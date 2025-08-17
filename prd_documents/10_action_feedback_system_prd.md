# Action Feedback System PRD

## Overview
Implement a comprehensive feedback loop where action approvals, denials, and edits trigger automatic agent responses to customers, with real-time status updates in conversation bubbles.

## Current State Analysis

### Frontend Action Handling
- **Actions Page**: `handleApprove()`, `handleDeny()` functions update action status
- **Database Service**: `updateActionStatus()` function handles status changes
- **Action Bubbles**: Display in conversations but don't reflect real-time status changes
- **Current Flow**: Frontend → Database → End (no agent notification)

### Missing Components
1. **Backend Notification**: No webhook to notify agent of action status changes
2. **Agent Response Generation**: No automatic responses to customers based action outcomes
3. **Real-time Status Updates**: Action bubbles don't reflect status changes
4. **Response Templates**: No structured response system for different action types

## Proposed Solution

### 1. Backend Agent Notification System

**New Endpoint**: `/action-feedback`
```python
@app.post("/action-feedback")
async def handle_action_feedback(request: Request):
    """
    Receive action status updates and trigger agent responses.
    """
    payload = await request.json()
    # Extract: action_id, status, user_response, contact_id, etc.
    # Generate contextual agent response
    # Send response via WhatsApp
    # Update action indicator message status
```

**Agent Response Logic**:
- Load action details from database
- Generate contextual response based on action type and outcome
- Send response to customer via WhatsApp
- Update conversation with status change

### 2. Frontend Integration

**Enhanced Action Handlers**:
```typescript
const handleApprove = async (actionId: number) => {
    // Current database update
    const success = await db.updateActionStatus(actionId, 'approved', replyText)
    
    if (success) {
        // NEW: Send feedback to agent
        await db.sendActionFeedback(actionId, 'approved', replyText)
        // Rest of current logic...
    }
}
```

**New Database Service Method**:
```typescript
async sendActionFeedback(
    actionId: number, 
    status: string, 
    userResponse?: string
): Promise<boolean>
```

### 3. Real-time Status Updates

**Enhanced Action Bubble**:
- Subscribe to action status changes
- Update badge/status indicator in real-time
- Show "Approved", "Denied", "Processing" states

**Database Triggers**:
- Create trigger on `actions` table updates
- Notify frontend via Supabase real-time
- Update action indicator messages automatically

### 4. Agent Response Templates

**Response Generation Logic**:
```python
def generate_action_response(action_type: str, status: str, user_response: str = "") -> str:
    templates = {
        'refund_request': {
            'approved': f"Great news! Your refund request has been approved. {user_response}",
            'denied': f"I understand your refund request. {user_response}"
        },
        'policy_clarification': {
            'approved': f"I've got the clarification you needed: {user_response}",
            'denied': f"Let me help clarify our policy: {user_response}"
        }
        # ... more templates
    }
```

## Implementation Plan

### Phase 1: Backend Agent Notification
1. Create `/action-feedback` endpoint
2. Implement agent response generation
3. Add WhatsApp sending logic
4. Test with manual payload

### Phase 2: Frontend Integration  
1. Add `sendActionFeedback()` to database service
2. Update `handleApprove()` and `handleDeny()` functions
3. Test frontend → backend notification flow

### Phase 3: Real-time Status Updates
1. Enhance ActionBubble component with status subscription
2. Update action indicator message status in database
3. Implement real-time UI updates

### Phase 4: Response Templates & Polish
1. Create comprehensive response templates
2. Add error handling and fallbacks
3. Implement logging and monitoring
4. End-to-end testing

## Database Schema Changes

### New Table: `action_responses` (Optional)
```sql
CREATE TABLE action_responses (
    id SERIAL PRIMARY KEY,
    action_id INTEGER REFERENCES actions(id),
    response_text TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT NOW(),
    whatsapp_message_id TEXT,
    status TEXT DEFAULT 'sent'
);
```

### Enhanced Messages Table
- Use existing `internal` message direction
- Add new `message_type`: `action_status_update`
- Store action status changes as internal messages

## Success Metrics

1. **Response Time**: Action approval → Customer response < 30 seconds
2. **Status Accuracy**: Action bubbles reflect correct status 100% of time
3. **Customer Experience**: Contextual responses based on action type
4. **Reliability**: 99%+ success rate for agent notifications

## Technical Architecture

```
Frontend Action Approval
↓
Database Status Update
↓
Webhook to Backend (/action-feedback)
↓ 
Agent Response Generation
↓
WhatsApp Message Sent
↓
Action Bubble Status Update (Real-time)
↓
Customer Receives Contextual Response
```

## Risk Mitigation

1. **Webhook Failures**: Graceful degradation, status still updates in UI
2. **Agent Response Errors**: Fallback to generic responses
3. **WhatsApp API Limits**: Queue system for high-volume scenarios
4. **Real-time Sync Issues**: Periodic status reconciliation

## Testing Strategy

1. **Unit Tests**: Response generation, webhook handling
2. **Integration Tests**: Frontend → Backend → WhatsApp flow  
3. **E2E Tests**: Complete user journey with real action
4. **Load Tests**: Multiple simultaneous action approvals
5. **Manual Tests**: Various action types and edge cases