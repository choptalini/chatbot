-- ================================================================
-- PHASE 1 ROLLBACK: Remove New Core Tables
-- ================================================================
-- This script removes all tables created in Phase 1
-- Use this if Phase 1 needs to be rolled back
-- WARNING: This will permanently delete the tables and all data
-- ================================================================

-- Drop tables in reverse dependency order to avoid foreign key conflicts

-- 1. Drop conversation_instructions (references chatbots and users)
DROP TABLE IF EXISTS conversation_instructions CASCADE;

-- 2. Drop bot_knowledge_base (references chatbots and users)
DROP TABLE IF EXISTS bot_knowledge_base CASCADE;

-- 3. Drop chatbots (references users)
DROP TABLE IF EXISTS chatbots CASCADE;

-- 4. Drop user_subscriptions (references users)
DROP TABLE IF EXISTS user_subscriptions CASCADE;

-- 5. Drop users (base table)
DROP TABLE IF EXISTS users CASCADE;

-- ================================================================
-- VALIDATION QUERIES
-- ================================================================
-- Verify all tables were removed successfully
SELECT 
    schemaname, 
    tablename, 
    tableowner 
FROM pg_tables 
WHERE tablename IN ('users', 'user_subscriptions', 'chatbots', 'bot_knowledge_base', 'conversation_instructions')
    AND schemaname = 'public'
ORDER BY tablename;

-- Should return no rows if rollback was successful

-- ================================================================
-- ROLLBACK CONFIRMATION
-- ================================================================
PRINT 'Phase 1 rollback completed. All new tables removed.'; 