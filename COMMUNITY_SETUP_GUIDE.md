# Community Forum Setup Guide

## Issue: No Posts Showing

If you can't see any posts in the community section, follow these steps:

## Step 1: Create Forum Tables in Supabase

1. Go to your Supabase Dashboard
2. Navigate to SQL Editor
3. Run the SQL file: `archived_files/sql_schemas/create_community_forum.sql`

This will create:
- `forum_posts` table
- `forum_comments` table
- `forum_tags` table
- `forum_post_tags` junction table
- Default tags (General, Dating, Social Skills, etc.)
- RLS policies for security

## Step 2: Add Service Role Policies (Important!)

The current RLS policies only allow authenticated users via `auth.uid()`. For the service role to read posts, add these policies:

```sql
-- Allow service role to manage all forum content
CREATE POLICY "Service role can manage posts"
    ON forum_posts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can manage comments"
    ON forum_comments FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can manage tags"
    ON forum_tags FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can manage post tags"
    ON forum_post_tags FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

## Step 3: Create Your First Post

Option A: Via the App
1. Go to `/community`
2. Click "Create Post" button
3. Fill in title and content
4. Select tags
5. Submit!

Option B: Via SQL (for testing)
```sql
-- Replace YOUR_USER_ID with your actual user ID from auth.users
INSERT INTO forum_posts (user_id, title, content, is_pinned)
VALUES
    ('YOUR_USER_ID', 'Welcome to PathForge Community!', 'This is our first post. Feel free to share your experiences and ask questions!', true);
```

To find your user ID:
```sql
SELECT id, email FROM auth.users LIMIT 1;
```

## Step 4: Verify Data

Check if posts exist:
```sql
SELECT id, title, user_id, created_at FROM forum_posts;
```

Check if tags exist:
```sql
SELECT * FROM forum_tags;
```

## Troubleshooting

### Error: "relation forum_posts does not exist"
- Run the SQL migration from Step 1

### Error: "new row violates row-level security policy"
- Add the service role policies from Step 2

### Posts exist but not showing
- Check browser console for errors
- Verify SUPABASE_SERVICE_ROLE_KEY is set in your .env
- Make sure you've restarted the server after adding the key

### Still no posts?
- Check the network tab in browser dev tools
- Look for failed API requests to `/rest/v1/forum_posts`
- Check the response body for error messages

## Testing the Community

1. Create a test post
2. Add a comment to the post
3. Try filtering by tags
4. Check that view counts increment
5. Test creating posts as different users

## Default Tags Available

After running the SQL migration, you'll have these tags:
- 🔥 General
- ❤️ Dating
- 💬 Social Skills
- 💪 Confidence
- 💑 Relationships
- ✨ Success Stories
- ❓ Questions
- 🧠 Inner Game

## Next Steps

Once posts are showing:
- Encourage users to create posts
- Pin important community guidelines
- Monitor and moderate content
- Add more tags as needed
