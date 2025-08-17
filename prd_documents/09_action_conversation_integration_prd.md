# Action-Conversation Integration PRD — Bidirectional Action Linking & Visual Indicators

## 1) Executive Summary
Implement full bidirectional integration between Actions and Conversations, allowing users to:
- Click "View Conversation" from action cards to jump to the exact conversation
- See action indicators as special message bubbles in conversation flow  
- Click action bubbles to navigate back to the specific action
- View real-time status updates (pending → approved/denied) in conversation

## 2) Problem Statement
Currently, actions and conversations are disconnected:
- "View Conversation" button in actions is non-functional
- No visual indication in conversations when actions are created
- No way to trace the conversation context that led to an action
- Operators can't see the full customer interaction timeline including actions

## 3) Goals & Success Criteria

### Primary Goals
1. **Functional View Conversation**: Action cards link directly to related conversations
2. **Action Indicators in Chat**: Special message bubbles show when actions are created
3. **Bidirectional Navigation**: Click action bubbles to return to action details
4. **Real-time Status Updates**: Action status changes reflect in conversation immediately
5. **Context Preservation**: Maintain conversation flow with action timeline

### Success Criteria
- ✅ "View Conversation" opens correct conversation at right scroll position
- ✅ Action creation adds visual indicator in conversation timeline
- ✅ Action indicators are internal-only (never sent to customers)  
- ✅ Clicking action bubbles navigates to specific action
- ✅ Status changes (approved/denied) update conversation indicators
- ✅ Action bubbles integrate seamlessly with existing message UI

## 4) Technical Architecture

### 4.1) Data Storage Strategy

#### Option A: Messages Table Integration (Recommended)
```sql
-- Add new message_type for action indicators
-- message_type: 'action_indicator' (new type)
-- direction: 'internal' (new direction)
-- ai_processed: false
-- user_sent: false  
-- content_text: JSON string with action details
-- metadata: { action_id, action_type, status }
```

#### Option B: Separate Action Events Table
```sql
-- Create new table for action events
CREATE TABLE action_events (
  id SERIAL PRIMARY KEY,
  action_id INTEGER REFERENCES actions(id),
  contact_id INTEGER REFERENCES contacts(id),
  message_position TIMESTAMP, -- When to show in timeline
  event_type VARCHAR(50), -- 'created', 'approved', 'denied'
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Recommendation**: Option A (Messages Table) for simplicity and timeline integration.

### 4.2) Message Structure for Action Indicators

```typescript
interface ActionIndicatorMessage {
  id: number
  contact_id: number
  direction: 'internal'  // New direction type
  message_type: 'action_indicator'  // New message type
  content_text: string  // JSON string with action details
  metadata: {
    action_id: number
    action_type: string
    action_status: 'pending' | 'approved' | 'denied'
    action_priority: string
  }
  created_at: string
  ai_processed: false
  user_sent: false
}
```

### 4.3) Component Architecture

#### Action Bubble Component
```typescript
interface ActionBubbleProps {
  actionId: number
  actionType: string
  status: 'pending' | 'approved' | 'denied'
  priority: string
  createdAt: string
  onClick: (actionId: number) => void
}
```

#### Updated Conversation Component
- Filter out 'internal' messages from WhatsApp sending
- Render action bubbles between regular messages
- Handle click navigation to actions page
- Subscribe to action status updates

## 5) Implementation Plan

### Phase 1: Database Schema & Backend Changes
1. **Extend message types and directions**
   - Add 'action_indicator' to message_type enum
   - Add 'internal' to direction enum (if needed)
   - Ensure WhatsApp sending filters exclude internal messages

2. **Update submit_action_request tool**
   - After creating action, insert action indicator message
   - Include action metadata in message content
   - Link to correct contact and conversation

3. **Update action status updates**  
   - When action approved/denied, update indicator message
   - Trigger realtime updates for conversation

### Phase 2: Frontend - Actions to Conversations Navigation
1. **Fix "View Conversation" button**
   - Resolve contact.thread_id to conversation
   - Navigate to conversations page with contact pre-selected
   - Auto-scroll to action indicator message (if implemented)

2. **Add conversation context to actions**
   - Store message timestamp or position reference
   - Enable deep-linking to specific conversation moments

### Phase 3: Frontend - Action Indicators in Conversations  
1. **Create ActionBubble component**
   - Design special message bubble for actions
   - Show action type, priority, and status
   - Include click handler for navigation

2. **Update ConversationsPage**
   - Detect 'action_indicator' message types
   - Render ActionBubble instead of regular message
   - Filter internal messages from WhatsApp integration

3. **Add action navigation handler**
   - Navigate to actions page with specific action selected
   - Maintain conversation context for back navigation

### Phase 4: Real-time Updates & Polish
1. **Realtime status synchronization**
   - Action status changes update conversation indicators
   - Bidirectional subscription between actions and conversations

2. **UI/UX Polish**
   - Smooth transitions between actions and conversations
   - Visual feedback for navigation actions
   - Accessibility and mobile responsiveness

## 6) Detailed Implementation Tasks

### 6.1) Backend Changes

#### Database Schema Updates
```sql
-- Add new enum values (if using enums)
ALTER TYPE message_type_enum ADD VALUE 'action_indicator';
ALTER TYPE direction_enum ADD VALUE 'internal';

-- Or update check constraints if using VARCHAR
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_direction_check;
ALTER TABLE messages ADD CONSTRAINT messages_direction_check 
  CHECK (direction IN ('incoming', 'outgoing', 'manual', 'internal'));

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_message_type_check;  
ALTER TABLE messages ADD CONSTRAINT messages_message_type_check
  CHECK (message_type IN ('text', 'image', 'audio', 'document', 'location', 'action_indicator'));
```

#### Update submit_action_request Tool
```python
# After successful action creation
def _create_action_indicator_message(action_id, contact_id, action_data):
    message_content = {
        "action_id": action_id,
        "action_type": action_data["request_type"], 
        "action_status": "pending",
        "action_priority": action_data["priority"],
        "action_details": action_data["request_details"][:100] + "..." # Truncated
    }
    
    # Insert indicator message  
    db.log_message(
        contact_id=contact_id,
        message_id=f"action_{action_id}_{int(time.time())}",
        direction='internal',
        message_type='action_indicator', 
        chatbot_id=action_data["chatbot_id"],
        content_text=json.dumps(message_content),
        metadata={"action_id": action_id},
        ai_processed=False,
        user_sent=False
    )
```

#### Update WhatsApp Message Filtering
```python
# Ensure internal messages are never sent to WhatsApp
def should_send_to_whatsapp(message):
    return message.direction != 'internal'
```

### 6.2) Frontend Changes

#### ActionBubble Component
```typescript
// components/ui/action-bubble.tsx
export function ActionBubble({ actionId, actionType, status, priority, createdAt, onClick }: ActionBubbleProps) {
  const getStatusColor = (status: string) => {
    switch(status) {
      case 'pending': return 'bg-yellow-100 border-yellow-300 text-yellow-800'
      case 'approved': return 'bg-green-100 border-green-300 text-green-800' 
      case 'denied': return 'bg-red-100 border-red-300 text-red-800'
      default: return 'bg-gray-100 border-gray-300 text-gray-800'
    }
  }

  return (
    <div className="flex justify-center my-4">
      <div 
        className={`max-w-md p-3 rounded-lg border-2 cursor-pointer hover:shadow-md transition-shadow ${getStatusColor(status)}`}
        onClick={() => onClick(actionId)}
      >
        <div className="flex items-center space-x-2">
          <Zap className="h-4 w-4" />
          <span className="font-medium">Action Created: {getActionTypeDisplay(actionType)}</span>
        </div>
        <div className="text-sm mt-1">
          Priority: {priority} • Status: {status} • Click to view details
        </div>
        <div className="text-xs text-gray-600 mt-1">
          {formatRelativeTime(createdAt)}
        </div>
      </div>
    </div>
  )
}
```

#### Update ConversationsPage  
```typescript
// In message rendering logic
const renderMessage = (message: Message) => {
  if (message.message_type === 'action_indicator') {
    const actionData = JSON.parse(message.content_text || '{}')
    return (
      <ActionBubble
        key={message.id}
        actionId={actionData.action_id}
        actionType={actionData.action_type}
        status={actionData.action_status}
        priority={actionData.action_priority}
        createdAt={message.created_at}
        onClick={handleActionClick}
      />
    )
  }
  
  // Regular message rendering...
}

const handleActionClick = (actionId: number) => {
  // Store current conversation context
  localStorage.setItem('returnToConversation', JSON.stringify({
    contactId: selectedConversation?.id,
    scrollPosition: messagesContainerRef.current?.scrollTop
  }))
  
  // Navigate to actions page with specific action
  localStorage.setItem('openActionId', actionId.toString())
  setCurrentPage('Actions') // or use router navigation
}
```

#### Update ActionsPage for Back Navigation
```typescript
// In ActionsPage component
useEffect(() => {
  const targetActionId = localStorage.getItem('openActionId')
  if (targetActionId) {
    // Scroll to or highlight specific action
    const actionElement = document.getElementById(`action-${targetActionId}`)
    actionElement?.scrollIntoView({ behavior: 'smooth' })
    localStorage.removeItem('openActionId')
  }
}, [actions])

// Update View Conversation button
const handleViewConversation = (action: Action) => {
  if (action.contact?.thread_id) {
    localStorage.setItem('openConversationContactId', action.contact_id.toString())
    setCurrentPage('Conversations') // or use router navigation
  }
}
```

## 7) UI/UX Design Specifications

### Action Bubble Design
- **Shape**: Rounded rectangle with subtle border
- **Position**: Centered in conversation, distinct from user/bot messages
- **Color Coding**: 
  - Pending: Yellow/amber theme
  - Approved: Green theme  
  - Denied: Red theme
- **Content**: Action type + priority + status + timestamp
- **Interaction**: Hover effects + click cursor
- **Size**: Compact but readable, max-width constrained

### Navigation Flow
1. **Actions → Conversations**: 
   - Click "View Conversation" → Opens conversation with contact
   - Auto-scroll to action indicator (if visible)
   - Highlight action bubble briefly
   
2. **Conversations → Actions**:
   - Click action bubble → Navigate to actions page
   - Highlight/scroll to specific action
   - Breadcrumb or back button to return

### Status Update Animation  
- Real-time status changes trigger smooth color transition
- Brief highlight/pulse effect on status change
- Update timestamp and status text

## 8) Data Flow & API Changes

### Action Creation Flow
```
1. WhatsApp Agent creates action via submit_action_request
2. Action inserted into actions table
3. Action indicator message inserted into messages table  
4. Realtime notification sent to conversations page
5. Action bubble appears in conversation timeline
```

### Status Update Flow  
```
1. Operator approves/denies action in Actions page
2. Action status updated in actions table
3. Corresponding action indicator message updated
4. Realtime update sent to conversations page
5. Action bubble status/color updates in conversation
```

### Navigation Flow
```
Action Card → "View Conversation" → ConversationsPage (contact selected)
Action Bubble ← Click ← ConversationsPage → ActionsPage (action highlighted)
```

## 9) Security & Performance Considerations

### Security
- **Internal messages never sent to customers**: Strict filtering in WhatsApp integration
- **RLS policies**: Action indicator messages respect same user permissions
- **Input validation**: Action metadata properly sanitized in message content

### Performance  
- **Message filtering**: Efficient queries to separate internal vs external messages
- **Lazy loading**: Action bubbles rendered on-demand in conversation scroll
- **Realtime optimization**: Targeted subscriptions for action status changes

## 10) Testing Strategy

### Unit Tests
- ActionBubble component rendering with different statuses
- Message filtering logic (internal vs external)
- Navigation handlers and state management
- Action indicator message creation

### Integration Tests
- End-to-end action creation → conversation indicator → navigation
- Realtime status updates across both pages
- WhatsApp message filtering (ensure internals never sent)
- Deep linking and context preservation

### Manual Testing Scenarios
1. Create action via WhatsApp agent → Verify indicator appears in conversation
2. Navigate from action to conversation → Verify correct contact/scroll
3. Navigate from conversation to action → Verify correct action highlighted  
4. Approve/deny action → Verify conversation indicator updates
5. Multiple actions in same conversation → Verify timeline accuracy

## 11) Rollout Plan

### Phase 1: Backend Foundation (Week 1)
- [ ] Database schema updates (message types/directions)
- [ ] Update submit_action_request tool to create indicators
- [ ] Ensure WhatsApp filtering excludes internal messages
- [ ] Test action indicator creation

### Phase 2: View Conversation (Week 1) 
- [ ] Implement "View Conversation" button functionality
- [ ] Add conversation navigation from actions
- [ ] Test bidirectional navigation basics

### Phase 3: Action Bubbles (Week 2)
- [ ] Create ActionBubble component
- [ ] Update ConversationsPage to render action indicators  
- [ ] Implement action bubble click navigation
- [ ] Test conversation timeline integration

### Phase 4: Real-time & Polish (Week 2)
- [ ] Add real-time status updates
- [ ] Polish UI transitions and animations
- [ ] Comprehensive testing and bug fixes
- [ ] Performance optimization

## 12) Success Metrics

### Functional Metrics
- **Navigation success rate**: >99% successful transitions between actions/conversations
- **Real-time latency**: <2 seconds for status updates to appear
- **Message filtering accuracy**: 100% internal messages filtered from WhatsApp
- **UI responsiveness**: <300ms for bubble interactions

### User Experience Metrics  
- **Context preservation**: Users can trace full customer interaction timeline
- **Workflow efficiency**: Reduced time to understand action context
- **Error reduction**: Fewer missed actions due to better visibility

## 13) Future Enhancements

### Advanced Features
- **Action threads**: Group related actions in conversation
- **Action templates**: Quick action creation from conversation
- **Smart summaries**: AI-generated action context from conversation
- **Bulk actions**: Handle multiple actions from single conversation

### Analytics Integration
- **Action conversion tracking**: From conversation events to actions
- **Response time metrics**: Time from action creation to resolution
- **Context effectiveness**: How conversation context helps action resolution

## 14) Implementation Checklist

### Database & Backend
- [ ] Update message table schema (types/directions)
- [ ] Modify submit_action_request tool for indicator creation
- [ ] Update action status handlers for indicator updates
- [ ] Ensure WhatsApp filtering excludes internal messages
- [ ] Add RLS policies for action indicator messages

### Frontend Components
- [ ] Create ActionBubble component with status styling
- [ ] Update Message rendering logic for action indicators
- [ ] Implement action bubble click navigation
- [ ] Fix "View Conversation" button in actions

### Navigation & State Management
- [ ] Add deep linking support for actions/conversations  
- [ ] Implement context preservation for back navigation
- [ ] Add loading states and error handling
- [ ] Test mobile responsiveness

### Real-time & Integration
- [ ] Set up realtime subscriptions for action status
- [ ] Test bidirectional updates between pages
- [ ] Verify message filtering in all WhatsApp flows
- [ ] Performance testing with multiple actions

### Testing & QA
- [ ] Unit tests for all new components
- [ ] Integration tests for navigation flows
- [ ] End-to-end testing of action lifecycle
- [ ] Mobile and accessibility testing

---

This comprehensive plan creates a seamless, intuitive integration between actions and conversations while maintaining security and performance. The action indicators will provide valuable context and improve operator workflow efficiency significantly.