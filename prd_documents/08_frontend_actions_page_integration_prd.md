# Frontend Actions Page Integration PRD — Real Database Connection

## 1) Executive Summary
Transform the current hardcoded Actions page in the SwiftReplies frontend to fetch real data from the database `actions` table. Replace static mock data with dynamic data fetching, maintain the existing UI/UX design, and add proper realtime updates via Supabase subscriptions.

## 2) Current State Analysis

### Frontend (SwiftReplies Frontend)
- **File**: `components/pages/actions-page.tsx`
- **Current State**: Uses hardcoded `actionCards` array with 4 mock actions
- **UI Components**: Well-designed responsive interface with filter buttons, action cards, and approve/deny functionality
- **Status**: UI complete but disconnected from database

### Backend (WhatsApp Folder)
- **Database**: PostgreSQL with `actions` table properly structured
- **Tool**: `submit_action_request` working and creating real actions in DB
- **Sample Data**: 2 real action requests exist in database from tool testing

### Database Schema (`actions` table)
```sql
- id: integer (PK, auto-increment)
- user_id: integer (FK to users)
- chatbot_id: integer (FK to chatbots)  
- contact_id: integer (FK to contacts)
- request_type: varchar (e.g., "refund_request", "policy_clarification")
- request_details: text (human-readable description)
- request_data: jsonb (structured context data)
- status: varchar ('pending', 'approved', 'denied', 'cancelled')
- user_response: text (operator response/instructions)
- response_data: jsonb (structured response data)
- priority: varchar ('low', 'medium', 'high', 'urgent')
- created_at: timestamp
- resolved_at: timestamp
- expires_at: timestamp
```

## 3) Problem Statement
The Actions Center frontend is completely disconnected from the real database, showing only mock data. Operators cannot see actual action requests created by the WhatsApp agent, and cannot approve/deny real requests, breaking the human-in-the-loop workflow.

## 4) Goals & Success Criteria

### Primary Goals
1. **Real Data Integration**: Replace mock data with actual database queries
2. **Maintain UI/UX**: Keep existing design, styling, and responsive behavior
3. **Realtime Updates**: Actions appear immediately when created by the agent
4. **Multi-tenant Support**: Show only actions for the current user's context
5. **Full CRUD Operations**: View, approve, deny, and respond to actions

### Success Criteria
- ✅ Actions page displays real actions from database
- ✅ Filter buttons (pending/approved/denied) work with real data
- ✅ Approve/deny buttons update database and UI
- ✅ Realtime subscriptions show new actions without refresh
- ✅ Contact information properly linked and displayed
- ✅ Response functionality works bidirectionally

## 5) Technical Implementation Plan

### 5.1) Database Service Extension (`lib/supabase/database.ts`)

#### Add Action Interface
```typescript
export interface Action {
  id: number
  user_id: number
  chatbot_id: number
  contact_id: number
  request_type: string
  request_details: string
  request_data?: Record<string, any>
  status: 'pending' | 'approved' | 'denied' | 'cancelled'
  user_response?: string
  response_data?: Record<string, any>
  priority: 'low' | 'medium' | 'high' | 'urgent'
  created_at: string
  resolved_at?: string
  expires_at?: string
  // Joined contact data
  contact?: Contact
}
```

#### Add Action Methods to DatabaseService
```typescript
class DatabaseService {
  // Get actions for current user with contact details
  async getActions(status?: string): Promise<Action[]>
  
  // Update action status (approve/deny)
  async updateActionStatus(
    actionId: number, 
    status: 'approved' | 'denied',
    userResponse?: string,
    responseData?: Record<string, any>
  ): Promise<boolean>
  
  // Get single action with full details
  async getActionById(actionId: number): Promise<Action | null>
  
  // Real-time subscription to actions for current user
  subscribeToActions(userId: number, callback: (action: Action) => void): () => void
}
```

### 5.2) Actions Page Component Updates (`components/pages/actions-page.tsx`)

#### State Management
```typescript
const [actions, setActions] = useState<Action[]>([])
const [loading, setLoading] = useState(true)
const [updating, setUpdating] = useState<Record<number, boolean>>({})
const [filter, setFilter] = useState<'pending' | 'approved' | 'denied'>('pending')
```

#### Data Fetching Logic
```typescript
useEffect(() => {
  loadActions()
  setupRealtimeSubscription()
  return () => cleanupSubscription()
}, [])

const loadActions = async () => {
  setLoading(true)
  try {
    const actionsData = await db.getActions(filter)
    setActions(actionsData)
  } catch (error) {
    toast({ title: "Error", description: "Failed to load actions" })
  } finally {
    setLoading(false)
  }
}
```

#### Action Handlers
```typescript
const handleApprove = async (actionId: number) => {
  const replyText = replyTexts[actionId] || ""
  setUpdating(prev => ({ ...prev, [actionId]: true }))
  
  try {
    const success = await db.updateActionStatus(actionId, 'approved', replyText)
    if (success) {
      setActions(prev => prev.map(a => 
        a.id === actionId 
          ? { ...a, status: 'approved', user_response: replyText, resolved_at: new Date().toISOString() }
          : a
      ))
      toast({ title: "Success", description: "Action approved successfully" })
    }
  } catch (error) {
    toast({ title: "Error", description: "Failed to approve action" })
  } finally {
    setUpdating(prev => ({ ...prev, [actionId]: false }))
  }
}
```

### 5.3) Realtime Integration

#### Supabase Subscription Setup
```typescript
const setupRealtimeSubscription = () => {
  const subscription = supabase
    .channel('actions')
    .on('postgres_changes', 
      { 
        event: 'INSERT', 
        schema: 'public', 
        table: 'actions',
        filter: `user_id=eq.${userId}` 
      },
      handleNewAction
    )
    .on('postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public', 
        table: 'actions',
        filter: `user_id=eq.${userId}`
      },
      handleActionUpdate
    )
    .subscribe()
    
  return () => subscription.unsubscribe()
}
```

### 5.4) UI Data Mapping

#### Transform Database Actions to UI Format
```typescript
const transformActionToUIFormat = (action: Action) => ({
  id: action.id,
  type: getActionTypeDisplay(action.request_type),
  icon: getActionIcon(action.request_type),
  title: getActionTitle(action.request_type, action.request_data),
  description: action.request_details,
  contactName: action.contact?.name || extractContactName(action.request_data) || 'Unknown',
  contactPhone: action.contact?.phone_number || 'N/A',
  timestamp: formatRelativeTime(action.created_at),
  status: action.status,
  conversationId: action.contact?.thread_id || '',
  priority: action.priority,
  userResponse: action.user_response,
  requestData: action.request_data
})
```

## 6) Implementation Steps

### Phase 1: Database Service Extension
1. **Add Action interface** to `types` in database.ts
2. **Implement `getActions()` method** with JOIN to contacts table
3. **Implement `updateActionStatus()` method** for approve/deny
4. **Add helper methods** for action formatting and utilities
5. **Test database methods** independently

### Phase 2: Actions Page Integration  
1. **Replace hardcoded actionCards** with state management
2. **Add useEffect hooks** for data loading and realtime subscriptions
3. **Update filter logic** to work with real status values
4. **Implement approve/deny handlers** calling database methods
5. **Add loading and error states** with proper UI feedback

### Phase 3: UI/UX Enhancements
1. **Map database fields to UI display** (request_type → readable titles)
2. **Handle contact information** display and linking
3. **Add timestamp formatting** for created_at/resolved_at
4. **Implement conversation linking** (View Conversation button)
5. **Add response data display** for structured context

### Phase 4: Realtime & Polish
1. **Setup Supabase realtime subscriptions** for instant updates
2. **Add optimistic UI updates** for better UX
3. **Handle edge cases** (deleted contacts, expired actions)
4. **Add retry logic** for failed operations
5. **Performance optimization** (pagination if needed)

## 7) Data Flow Architecture

```
WhatsApp Agent (Backend)
    ↓ (creates action via submit_action_request tool)
PostgreSQL actions table
    ↓ (realtime trigger)
Supabase Realtime
    ↓ (subscription)
Frontend Actions Page
    ↓ (user interaction)
Database Service (approve/deny)
    ↓ (status update)
PostgreSQL actions table
    ↓ (realtime trigger)  
Frontend UI Update
```

## 8) Error Handling & Edge Cases

### Database Errors
- **Network failures**: Show retry buttons and offline indicators
- **Permission errors**: Clear error messages with auth guidance
- **Timeout errors**: Graceful degradation with cached data

### Data Consistency
- **Optimistic updates**: Update UI immediately, rollback on failure
- **Stale data**: Refresh actions when window regains focus
- **Concurrent updates**: Handle conflicts with latest-wins strategy

### Missing Dependencies
- **Deleted contacts**: Show placeholder contact info with ID
- **Invalid request_data**: Graceful handling of malformed JSON
- **Expired actions**: Visual indicators and auto-cleanup

## 9) Security Considerations

### Row Level Security (RLS)
- **Actions table**: Users can only see their own actions
- **Contact filtering**: Ensure contact_id belongs to current user
- **Update permissions**: Only action owner can approve/deny

### Input Validation
- **User responses**: Sanitize and validate text inputs
- **Status transitions**: Validate allowed status changes
- **Request data**: Parse JSON safely with error handling

## 10) Testing Strategy

### Unit Tests
- Database service methods (getActions, updateActionStatus)
- UI component rendering with mock data
- Action transformation and formatting utilities
- Error handling and edge cases

### Integration Tests  
- End-to-end action creation → display → approval flow
- Realtime subscription updates
- Multi-user isolation and permissions
- Performance with large action datasets

### Manual Testing
- Create actions via WhatsApp agent tool
- Verify immediate appearance in frontend
- Test approve/deny workflow with responses
- Validate filtering and status changes

## 11) Performance Considerations

### Query Optimization
- **Index on user_id + status** for fast filtering
- **LIMIT queries** to prevent large data loads
- **JOIN optimization** for contact information
- **Caching strategy** for frequently accessed data

### Frontend Performance
- **Virtualization** for large action lists (if needed)
- **Debounced updates** for realtime subscriptions
- **Lazy loading** of contact details
- **Optimistic UI updates** for responsiveness

## 12) Rollout Plan

### Phase 1: Development (Week 1)
- Implement database service methods
- Update actions page with real data fetching
- Basic approve/deny functionality

### Phase 2: Integration (Week 1)
- Add realtime subscriptions
- Polish UI/UX with proper loading states
- Handle edge cases and errors

### Phase 3: Testing (Week 1)
- End-to-end testing with real agent workflows
- Performance testing with multiple actions
- Security and permission validation

### Phase 4: Production (Week 1)
- Deploy to production environment
- Monitor realtime updates and performance
- Gather user feedback and iterate

## 13) Success Metrics

### Functional Metrics
- **Actions displayed**: 100% of database actions visible in UI
- **Realtime latency**: < 2 seconds from creation to display
- **Operation success rate**: > 99% for approve/deny actions
- **UI responsiveness**: < 500ms for all user interactions

### User Experience Metrics
- **Time to action**: < 30 seconds from agent request to operator response
- **Error rate**: < 1% of operations result in user-facing errors
- **User satisfaction**: Positive feedback on action management workflow

## 14) Future Enhancements

### Advanced Features
- **Bulk operations**: Approve/deny multiple actions at once
- **Action templates**: Pre-defined responses for common requests
- **Escalation rules**: Auto-escalate high-priority actions
- **Action analytics**: Metrics on response times and patterns

### Integration Opportunities
- **Notification system**: Push notifications for urgent actions
- **Mobile app**: Native mobile interface for action management
- **Webhook integration**: External system notifications
- **AI suggestions**: Smart response recommendations

## 15) Dependencies & Prerequisites

### Technical Dependencies
- ✅ **Database schema**: Actions table already exists and populated
- ✅ **Supabase client**: Already configured and working
- ✅ **Database service**: Pattern established in existing code
- ✅ **UI components**: All necessary components already available

### Business Dependencies
- ✅ **Agent tool**: submit_action_request working and creating actions
- ✅ **User authentication**: Multi-tenant user system operational
- ✅ **Contact management**: Contact linking and display working

## 16) Implementation Checklist

- [ ] **Add Action interface** to database.ts types
- [ ] **Implement getActions() method** with contact JOIN
- [ ] **Implement updateActionStatus() method** for approve/deny
- [ ] **Add realtime subscription helpers** for actions
- [ ] **Update actions-page.tsx** to use real data
- [ ] **Replace hardcoded actionCards** with database state
- [ ] **Implement loading and error states** with proper UI
- [ ] **Add approve/deny handlers** calling database service
- [ ] **Setup realtime subscriptions** for instant updates
- [ ] **Test end-to-end workflow** from agent to frontend
- [ ] **Add proper error handling** and user feedback
- [ ] **Performance optimization** and edge case handling

## 17) Files to Modify

### Primary Files
- `lib/supabase/database.ts` - Add Action interface and methods
- `components/pages/actions-page.tsx` - Replace mock data with real data

### Supporting Files  
- `types/actions.ts` - Type definitions (if needed)
- `lib/utils/action-formatters.ts` - Display formatting helpers
- `hooks/use-actions.ts` - Custom hook for action management (optional)

### Test Files
- `__tests__/database/actions.test.ts` - Database service tests
- `__tests__/components/actions-page.test.tsx` - Component tests

---

This PRD provides a comprehensive roadmap for connecting the Actions page to real database data while maintaining the existing excellent UI/UX design. The implementation preserves all current styling and functionality while adding the critical database integration needed for the human-in-the-loop workflow.