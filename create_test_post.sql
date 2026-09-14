-- ============================================================
-- Quick Test Post Creator
-- ============================================================
-- This will create a test post using your first user account

-- Step 1: Check if you have users
SELECT 'Your users:' AS info;
SELECT id, email, created_at FROM auth.users ORDER BY created_at LIMIT 5;

-- Step 2: Create a welcome post automatically
-- This uses your first user as the author
INSERT INTO forum_posts (user_id, title, content, is_pinned, views, likes)
SELECT
    u.id,
    '🎉 Welcome to the PathForge Community!',
    E'Hey everyone! 👋\n\nWelcome to our community forum. This is a space where we can:\n\n• Share experiences and insights\n• Ask questions and get advice\n• Celebrate wins and successes\n• Support each other on our journeys\n\nFeel free to introduce yourself and start conversations. Let''s grow together!\n\n- The PathForge Team',
    true,
    42,
    15
FROM auth.users u
ORDER BY created_at
LIMIT 1;

-- Step 3: Add a General tag to the post
INSERT INTO forum_post_tags (post_id, tag_id)
SELECT
    fp.id,
    ft.id
FROM forum_posts fp
CROSS JOIN forum_tags ft
WHERE ft.name = 'General'
AND NOT EXISTS (
    SELECT 1 FROM forum_post_tags fpt
    WHERE fpt.post_id = fp.id AND fpt.tag_id = ft.id
)
LIMIT 1;

-- Step 4: Create a second example post
INSERT INTO forum_posts (user_id, title, content, views, likes)
SELECT
    u.id,
    'How do you handle nervousness in social situations?',
    E'I''ve been working on my social skills and one thing I still struggle with is nervousness when meeting new people.\n\nWhat techniques have worked for you? I''d love to hear your experiences!',
    28,
    8
FROM auth.users u
ORDER BY created_at
LIMIT 1;

-- Step 5: Tag the second post
INSERT INTO forum_post_tags (post_id, tag_id)
SELECT
    fp.id,
    ft.id
FROM forum_posts fp
CROSS JOIN forum_tags ft
WHERE ft.name = 'Questions'
AND fp.title LIKE '%nervousness%'
AND NOT EXISTS (
    SELECT 1 FROM forum_post_tags fpt
    WHERE fpt.post_id = fp.id AND fpt.tag_id = ft.id
)
LIMIT 1;

-- Step 6: Add a comment to the question
INSERT INTO forum_comments (post_id, user_id, content, likes)
SELECT
    fp.id,
    u.id,
    E'Great question! I find that deep breathing helps a lot. Before any social interaction, I take 3 deep breaths and remind myself that everyone feels nervous sometimes. 😊',
    5
FROM forum_posts fp
CROSS JOIN auth.users u
WHERE fp.title LIKE '%nervousness%'
ORDER BY u.created_at
LIMIT 1;

-- Step 7: Verify posts were created
SELECT 'Posts created!' AS status;
SELECT
    fp.id,
    fp.title,
    fp.is_pinned,
    fp.views,
    fp.likes,
    u.email as author,
    (SELECT COUNT(*) FROM forum_comments WHERE post_id = fp.id) as comment_count
FROM forum_posts fp
LEFT JOIN auth.users u ON fp.user_id = u.id
ORDER BY fp.created_at DESC;

SELECT '✓ Done! Refresh your /community page to see the posts!' AS final_message;
