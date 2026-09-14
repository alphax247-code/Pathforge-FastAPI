-- ============================================================
-- Community Forum Debug Script
-- ============================================================
-- Run this to check what's wrong with the forum setup

-- ============================================================
-- 1. Check if tables exist
-- ============================================================
SELECT 'Checking tables...' AS status;

SELECT tablename, schemaname
FROM pg_tables
WHERE tablename IN ('forum_posts', 'forum_comments', 'forum_tags', 'forum_post_tags')
ORDER BY tablename;

-- Expected: Should show 4 tables (forum_posts, forum_comments, forum_tags, forum_post_tags)

-- ============================================================
-- 2. Check if tags exist
-- ============================================================
SELECT 'Checking tags...' AS status;

SELECT COUNT(*) as tag_count FROM forum_tags;
SELECT name FROM forum_tags ORDER BY name;

-- Expected: Should show 8 tags

-- ============================================================
-- 3. Check if posts exist
-- ============================================================
SELECT 'Checking posts...' AS status;

SELECT COUNT(*) as post_count FROM forum_posts;

-- If count > 0, show the posts:
SELECT id, title, user_id, created_at, is_pinned
FROM forum_posts
ORDER BY created_at DESC;

-- ============================================================
-- 4. Check your user ID
-- ============================================================
SELECT 'Finding your user...' AS status;

SELECT id, email, created_at
FROM auth.users
ORDER BY created_at
LIMIT 5;

-- Copy your user ID from the results above

-- ============================================================
-- 5. Check RLS policies
-- ============================================================
SELECT 'Checking RLS policies...' AS status;

SELECT schemaname, tablename, policyname, permissive, roles, cmd
FROM pg_policies
WHERE tablename LIKE 'forum%'
ORDER BY tablename, policyname;

-- Expected: Should show policies including "Service role can manage posts"

-- ============================================================
-- 6. Test creating a post (IMPORTANT!)
-- ============================================================
-- Copy the results above, then run THIS section separately:
-- Replace 'PASTE_YOUR_USER_ID_HERE' with your actual user ID

/*
DO $$
DECLARE
    v_user_id UUID := 'PASTE_YOUR_USER_ID_HERE';  -- REPLACE THIS!
    v_post_id UUID;
BEGIN
    -- Create a test post
    INSERT INTO forum_posts (user_id, title, content, is_pinned, views, likes)
    VALUES (
        v_user_id,
        '🚀 Test Post - Forum is Working!',
        'This is a test post to verify the forum is set up correctly. If you can see this, everything is working!',
        true,
        10,
        5
    )
    RETURNING id INTO v_post_id;

    RAISE NOTICE 'Post created successfully! ID: %', v_post_id;

    -- Add a tag
    INSERT INTO forum_post_tags (post_id, tag_id)
    SELECT v_post_id, id FROM forum_tags WHERE name = 'General' LIMIT 1;

    RAISE NOTICE 'Tag added successfully!';
END $$;
*/

-- After running the above, check if post was created:
SELECT COUNT(*) as posts_after_insert FROM forum_posts;

-- ============================================================
-- 7. Final verification
-- ============================================================
SELECT 'Final check...' AS status;

-- Show all posts with details
SELECT
    fp.id,
    fp.title,
    fp.content,
    fp.is_pinned,
    fp.views,
    fp.likes,
    fp.created_at,
    u.email as author_email
FROM forum_posts fp
LEFT JOIN auth.users u ON fp.user_id = u.id
ORDER BY fp.created_at DESC;

SELECT '✓ Debug complete! Check the results above.' AS status;
