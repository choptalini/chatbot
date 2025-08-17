# Enhanced Campaign Request System PRD

## Executive Summary

Transform the campaigns page from a basic hardcoded interface into a comprehensive campaign request system where users can submit detailed WhatsApp campaign requests for admin approval, including custom templates, interactive buttons, media uploads, and flexible targeting options.

## Current State Analysis

### Frontend (campaigns-page.tsx)
- **Existing**: Basic 4-step wizard with hardcoded data
- **Current Steps**: Name/Type → Audience → Message → Schedule
- **Missing**: Database integration, file uploads, template customization, approval workflow

### Database
- **Status**: `campaigns` table referenced but doesn't exist yet
- **Analytics**: Basic campaign tracking in dashboard analytics
- **Real-time**: Not configured for campaigns table

### Storage
- **Status**: No file upload functionality exists
- **Need**: Supabase Storage integration for campaign images

## Enhanced Campaign Request System Requirements

### 1. **Campaign Request Submission**

#### **Multi-Step Request Form (8 Steps)**

**Step 1: Campaign Basics**
- Campaign Name (required)
- Campaign Description (detailed, free text)
- Campaign Type (promotional, announcement, follow-up, product launch, event, custom)
- Requested Launch Date
- Priority Level (low, medium, high, urgent)

**Step 2: Platform & Targeting**
- Platform Selection: WhatsApp (primary), with future support for SMS, Email
- Target Audience (free text description of who they want to reach)
- Geographic Targeting (optional)
- Contact Filters (tags, segments, custom criteria in free text)
- Estimated Recipients (user estimate vs system calculation)

**Step 3: Template Configuration**
- Message Type: 
  - Simple Text
  - Rich Media (image + text)
  - Interactive Template (with buttons)
- Template Structure Selection:
  - Header Type: None, Text, Image, Video
  - Body Text (required, with variable support)
  - Footer Text (optional)
  - Button Configuration (if interactive)

**Step 4: Message Content**
- Header Content (text or upload media)
- Main Message Body (rich text editor with personalization)
- Footer Text
- Call-to-Action (if applicable)
- Personalization Variables ({name}, {phone}, {last_order}, etc.)

**Step 5: Interactive Elements (Optional)**
- Button Type: Call-to-Action, Quick Reply, URL
- Button Configuration:
  - Text for each button
  - Actions (URL, phone number, quick reply text)
  - Maximum 3 buttons per template
- Flow Logic (what happens after button click)

**Step 6: Media Upload**
- Image Upload (multiple files supported)
- File Requirements: Max 5MB, JPG/PNG/GIF
- Alt Text for accessibility
- Image optimization options
- Preview functionality

**Step 7: Campaign Details**
- Budget Estimate (user input)
- Expected ROI/Goals
- Success Metrics they want to track
- Special Instructions for admin
- Compliance Requirements

**Step 8: Review & Submit**
- Complete campaign preview
- Terms and conditions acceptance
- Final submission with admin notes

#### **Free-Form Input Philosophy**
- Most fields allow free text input for maximum flexibility
- Guided suggestions without forcing rigid categories
- Rich text editors where appropriate
- File upload with drag-and-drop interface

### 2. **Database Schema**

#### **campaigns Table**
```sql
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    chatbot_id INTEGER NOT NULL REFERENCES chatbots(id),
    
    -- Basic Info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    campaign_type VARCHAR(100),
    status campaign_status DEFAULT 'pending',
    priority priority_level DEFAULT 'medium',
    
    -- Targeting & Platform
    platform VARCHAR(50) DEFAULT 'whatsapp',
    target_audience TEXT, -- Free text description
    targeting_criteria JSONB, -- Flexible targeting data
    estimated_recipients INTEGER,
    actual_recipients INTEGER,
    
    -- Template Configuration
    template_type VARCHAR(50), -- 'text', 'media', 'interactive'
    template_structure JSONB, -- Header, body, footer, buttons config
    message_content JSONB, -- All content including media URLs
    
    -- Interactive Elements
    has_buttons BOOLEAN DEFAULT FALSE,
    buttons_config JSONB, -- Button definitions and actions
    
    -- Media Assets
    media_assets JSONB, -- Array of uploaded file URLs and metadata
    
    -- Campaign Details
    requested_launch_date TIMESTAMP,
    actual_launch_date TIMESTAMP,
    budget_estimate DECIMAL(10,2),
    expected_roi TEXT,
    success_metrics TEXT,
    special_instructions TEXT,
    
    -- Admin Fields
    admin_notes TEXT,
    admin_response TEXT,
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP,
    denied_reason TEXT,
    
    -- Performance Tracking
    sent_count INTEGER DEFAULT 0,
    delivered_count INTEGER DEFAULT 0,
    read_count INTEGER DEFAULT 0,
    clicked_count INTEGER DEFAULT 0,
    conversion_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Status enum
CREATE TYPE campaign_status AS ENUM (
    'draft', 'pending', 'reviewing', 'approved', 
    'scheduled', 'sending', 'sent', 'completed', 
    'denied', 'cancelled', 'expired'
);

-- Priority enum
CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'urgent');
```

#### **campaign_media Table** (for file management)
```sql
CREATE TABLE campaign_media (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    alt_text TEXT,
    upload_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3. **File Upload & Storage System**

#### **Supabase Storage Integration**
- **Bucket**: `campaign-media`
- **Structure**: `user_id/campaign_id/filename`
- **Security**: RLS policies for user isolation
- **File Types**: Images (JPG, PNG, GIF), Videos (MP4), Documents (PDF)
- **Size Limits**: 5MB per image, 10MB per video

#### **Upload Flow**
1. Client-side file validation
2. Generate unique filename with timestamp
3. Upload to Supabase Storage
4. Store URL and metadata in database
5. Real-time preview updates

### 4. **Enhanced Frontend Components**

#### **New Components Needed**
- `CampaignRequestForm` (8-step wizard)
- `MediaUploadZone` (drag-and-drop)
- `TemplatePreview` (WhatsApp template simulation)
- `ButtonBuilder` (interactive button configuration)
- `RichTextEditor` (message content with variables)
- `CampaignStatusCard` (request tracking)
- `AdminApprovalInterface` (admin-only)

#### **Updated Components**
- `CampaignsPage` (request listing + creation)
- Database service with campaign operations

### 5. **Approval Workflow Integration**

#### **Status Lifecycle**
```
draft → pending → reviewing → approved/denied
                 ↓
approved → scheduled → sending → sent → completed
```

#### **Admin Interface**
- Campaign request queue
- Detailed review interface
- Approval/denial with notes
- Template validation tools
- Cost estimation
- Scheduling interface

#### **Integration with Actions System**
- Campaign requests can trigger action requests
- Escalation for complex campaigns
- Admin feedback loop

### 6. **WhatsApp Template Validation**

#### **Template Compliance**
- WhatsApp Business API template requirements
- Message length limits
- Button count restrictions
- Media format validation
- Personalization variable validation

#### **Preview System**
- Real-time WhatsApp-style preview
- Multiple device sizes
- Dark/light mode preview
- Interactive button testing

### 7. **Real-time Updates**

#### **Broadcast Triggers**
```sql
-- Add to DATABASE_REALTIME_SETUP.sql
CREATE OR REPLACE FUNCTION public.broadcast_campaign_changes()
RETURNS TRIGGER
SECURITY DEFINER
LANGUAGE plpgsql
AS $$
DECLARE
    user_id_val INTEGER;
    topic_name TEXT;
BEGIN
    user_id_val := COALESCE(NEW.user_id, OLD.user_id);
    
    IF user_id_val IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    
    topic_name := 'campaigns:user:' || user_id_val;
    
    PERFORM realtime.broadcast_changes(
        topic_name,
        TG_OP,
        TG_OP,
        TG_TABLE_NAME,
        TG_TABLE_SCHEMA,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW END,
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD END
    );
    
    RETURN COALESCE(NEW, OLD);
END;
$$;
```

### 8. **API Endpoints**

#### **Frontend Database Service Methods**
```typescript
// Campaign CRUD operations
async createCampaignRequest(campaignData: CampaignRequest): Promise<{success: boolean, id?: number}>
async getCampaigns(status?: string): Promise<Campaign[]>
async getCampaignById(id: number): Promise<Campaign | null>
async updateCampaignStatus(id: number, status: string, notes?: string): Promise<boolean>
async uploadCampaignMedia(campaignId: number, files: FileList): Promise<string[]>
async deleteCampaignMedia(mediaId: number): Promise<boolean>

// Real-time subscriptions
subscribeToCampaigns(userId: number, callback: Function): Function
```

#### **Integration with Backend**
- Campaign execution via WhatsApp fetcher
- Template submission to WhatsApp Business API
- Performance tracking and analytics

## Implementation Phases

### Phase 1: Database & Core Structure (Week 1)
1. Create database tables and types
2. Set up Supabase Storage bucket
3. Configure RLS policies and real-time triggers
4. Basic database service methods

### Phase 2: Request Form (Week 2)
1. 8-step campaign request wizard
2. Form validation and state management
3. Media upload functionality
4. Template preview system

### Phase 3: Campaign Management (Week 3)
1. Campaign listing and filtering
2. Status tracking and real-time updates
3. Edit and clone functionality
4. Campaign analytics dashboard

### Phase 4: Admin Interface (Week 4)
1. Admin approval interface
2. Template validation tools
3. Campaign scheduling system
4. Performance tracking

### Phase 5: WhatsApp Integration (Week 5)
1. Template submission to WhatsApp API
2. Campaign execution system
3. Delivery tracking and analytics
4. A/B testing framework

## Success Metrics

### User Experience
- Campaign request completion rate > 80%
- Average request submission time < 10 minutes
- User satisfaction score > 4.5/5

### System Performance
- File upload success rate > 99%
- Real-time update latency < 2 seconds
- Template validation accuracy > 95%

### Business Impact
- Campaign approval time reduction by 60%
- Template compliance improvement
- Increased campaign submission volume

## Technical Considerations

### Security
- File upload validation and scanning
- RLS policies for multi-tenant isolation
- Input sanitization and XSS prevention
- Rate limiting for uploads and submissions

### Scalability
- Efficient image compression and optimization
- Pagination for large campaign lists
- Background processing for heavy operations
- CDN integration for media delivery

### Compliance
- WhatsApp Business API compliance
- GDPR compliance for user data
- File retention policies
- Audit logging for admin actions

This comprehensive system will transform the campaigns page into a powerful, user-friendly tool that gives users complete creative freedom while maintaining proper approval workflows and WhatsApp compliance.