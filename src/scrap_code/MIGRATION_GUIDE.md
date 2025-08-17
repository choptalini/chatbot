# 🚀 SwiftReplies.ai Multi-Tenant Migration Guide

This guide explains how to migrate your WhatsApp bot system from single-tenant to multi-tenant architecture.

## 📋 Pre-Migration Checklist

✅ **Database Migration Completed** - All 8 phases finished  
✅ **Admin User Created** - admin@swiftreplies.ai with unlimited subscription  
✅ **Existing Data Migrated** - 8 contacts and 614 messages preserved  
✅ **New Files Created** - Multi-tenant database and message fetcher ready  

## 🔄 Migration Steps

### Step 1: Backup Current System

**Important**: Before switching, backup your current working files:

```bash
# Create backup of current system
cp whatsapp_message_fetcher.py whatsapp_message_fetcher_backup.py
cp src/database.py src/database_backup.py
```

### Step 2: Update Environment Variables

Add these new environment variables to your `.env` file:

```bash
# Multi-tenant feature flags
ENABLE_MULTI_TENANT=true
ENABLE_USAGE_TRACKING=true
ENABLE_ACTIONS_CENTER=true

# Usage limits (optional - defaults provided)
DEFAULT_DAILY_MESSAGE_LIMIT=1000
DEFAULT_MONTHLY_MESSAGE_LIMIT=30000
DEFAULT_DAILY_CAMPAIGN_LIMIT=10
DEFAULT_MONTHLY_CAMPAIGN_LIMIT=300

# Bot configuration (optional - defaults provided)
DEBOUNCE_SECONDS=3
MAX_WORKERS=5
BUSY_THRESHOLD=3
```

### Step 3: Test the New System

**Option A: Side-by-side testing** (Recommended)
```bash
# Run new multi-tenant system on different port
python whatsapp_message_fetcher_multitenant.py --port 8001

# Keep original running on port 8000 as backup
python whatsapp_message_fetcher.py --port 8000
```

**Option B: Direct replacement** (After testing)
```bash
# Stop current system
pkill -f "whatsapp_message_fetcher.py"

# Start new multi-tenant system
python whatsapp_message_fetcher_multitenant.py
```

### Step 4: Verify Multi-Tenant Features

Test these new endpoints:

```bash
# Health check with multi-tenant metrics
curl http://localhost:8000/health

# System metrics
curl http://localhost:8000/metrics

# Send test message and verify it's logged correctly
```

### Step 5: Gradual Feature Enablement

You can gradually enable features by updating environment variables:

```bash
# Start with basic multi-tenant support
ENABLE_MULTI_TENANT=true
ENABLE_USAGE_TRACKING=false
ENABLE_ACTIONS_CENTER=false

# Then gradually enable more features
ENABLE_USAGE_TRACKING=true
ENABLE_ACTIONS_CENTER=true
```

## 📊 What Changed

### Database Changes
| Table | Old Schema | New Schema |
|-------|------------|------------|
| `contacts` | phone_number (unique) | phone_number + user_id (composite unique) |
| `messages` | basic fields | + chatbot_id, ai_processed, processing_duration |
| `orders` | basic fields | + user_id, total_amount, currency, payment_status |
| `campaigns` | basic fields | + user_id, campaign_stats, target_audience |

### New Tables Added
- **`users`** - Multi-tenant user accounts
- **`user_subscriptions`** - Custom subscription plans with JSONB config
- **`chatbots`** - Multiple chatbots per user
- **`actions`** - Human-in-the-loop action requests
- **`usage_tracking`** - Daily/monthly usage limits
- **`bot_knowledge_base`** - Custom Q&A per chatbot
- **`conversation_instructions`** - Dynamic bot instructions

### Code Structure
```
Old Structure:
├── whatsapp_message_fetcher.py
├── src/database.py
└── src/agent/core.py

New Structure:
├── whatsapp_message_fetcher_multitenant.py  # 🆕 Multi-tenant message fetcher
├── src/multi_tenant_database.py             # 🆕 Enhanced database operations
├── src/multi_tenant_config.py               # 🆕 Configuration management
├── src/database.py                          # 🔄 Kept for backward compatibility
└── src/agent/core.py                        # ✅ No changes needed
```

## 🔧 Key Features Added

### 1. **Multi-Tenant Data Isolation**
- Each contact belongs to a specific user
- Messages are associated with specific chatbots
- Complete data separation between tenants

### 2. **Usage Tracking & Limits**
```python
# Check if user can send more messages
usage_check = check_message_limits(user_id)
if not usage_check['within_limits']:
    # Handle limit exceeded
```

### 3. **Actions Center (Human-in-the-Loop)**
```python
# Create action request for human intervention
action_id = create_action_request(
    user_id=user_id,
    chatbot_id=chatbot_id,
    contact_id=contact_id,
    request_type="discount_approval",
    request_details="Customer asking for 25% discount",
    priority="medium"
)
```

### 4. **Enhanced Logging & Analytics**
- AI processing metrics (duration, confidence)
- Enhanced message metadata
- Usage analytics ready for dashboards

## 🔄 Backward Compatibility

The new system maintains **100% backward compatibility**:

```python
# Old functions still work
from src.multi_tenant_database import get_or_create_contact, log_message

# New functions available
from src.multi_tenant_database import (
    track_message_usage, 
    check_message_limits,
    create_action_request
)
```

## 📈 Testing Checklist

### ✅ Basic Functionality
- [ ] Incoming messages processed correctly
- [ ] Outgoing messages sent successfully  
- [ ] Contact creation/retrieval works
- [ ] Message logging includes new fields

### ✅ Multi-Tenant Features
- [ ] Messages assigned to correct user/chatbot
- [ ] Usage tracking increments properly
- [ ] Limits enforced when exceeded
- [ ] Action requests created when needed

### ✅ Performance
- [ ] Response times similar to old system
- [ ] Database queries optimized
- [ ] Worker scaling functions properly
- [ ] Memory usage stable

## 🚨 Troubleshooting

### Common Issues

**1. Database Connection Errors**
```bash
# Check if all tables exist
python -c "from src.multi_tenant_database import db; print(db.connect_to_db())"
```

**2. Import Errors**
```bash
# Install missing dependency
pip install psycopg2-binary
```

**3. Configuration Issues**
```python
# Validate configuration
from src.multi_tenant_config import config
print(config.validate_config())
```

**4. Migration Not Complete**
```bash
# Re-run final completion if needed
cd database_migration/scripts
python final_completion.py
```

## 🔄 Rollback Plan

If you need to rollback to the old system:

```bash
# Stop new system
pkill -f "whatsapp_message_fetcher_multitenant"

# Restore original files
cp whatsapp_message_fetcher_backup.py whatsapp_message_fetcher.py
cp src/database_backup.py src/database.py

# Start original system
python whatsapp_message_fetcher.py
```

**Important**: The database migration is **irreversible** but **safe**. All your existing data remains intact and accessible.

## 🎯 Next Steps After Migration

### Immediate (Day 1)
1. ✅ Verify all existing conversations work
2. ✅ Monitor system logs for errors
3. ✅ Test message sending/receiving

### Short Term (Week 1)
1. 🔧 Set up monitoring dashboards
2. 📊 Review usage analytics
3. 🔐 Change admin password
4. 📝 Document any custom configurations

### Long Term (Month 1+)
1. 🏗️ Build user management interface
2. 💳 Implement subscription billing
3. 📈 Create analytics dashboards  
4. 🤖 Configure multiple chatbots
5. 🎨 Customize per-tenant features

## 📞 Support

If you encounter issues during migration:

1. **Check the logs**: Look for detailed error messages
2. **Verify database**: Ensure all 20 tables exist
3. **Test connectivity**: Use health check endpoints
4. **Review configuration**: Validate all environment variables

---

**🎉 Congratulations!** Your WhatsApp bot is now ready for multi-tenant SaaS operations with unlimited scalability! 