-- ============================================================
-- PathForge Community Forum - Complete Setup with Sample Data
-- ============================================================
-- Run this in Supabase SQL Editor to set up the community forum

-- ============================================================
-- 1. Create Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS forum_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_locked BOOLEAN DEFAULT FALSE,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forum_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES forum_posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    parent_id UUID REFERENCES forum_comments(id) ON DELETE CASCADE,
    likes INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forum_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT DEFAULT '#D4AF37',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forum_post_tags (
    post_id UUID NOT NULL REFERENCES forum_posts(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES forum_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

-- ============================================================
-- 2. Create Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_forum_posts_user_id ON forum_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_created_at ON forum_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_comments_post_id ON forum_comments(post_id);
CREATE INDEX IF NOT EXISTS idx_forum_comments_user_id ON forum_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_forum_post_tags_post_id ON forum_post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_forum_post_tags_tag_id ON forum_post_tags(tag_id);

-- ============================================================
-- 3. Create Triggers
-- ============================================================

CREATE OR REPLACE FUNCTION update_forum_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_forum_posts_updated ON forum_posts;
CREATE TRIGGER trigger_forum_posts_updated
    BEFORE UPDATE ON forum_posts
    FOR EACH ROW
    EXECUTE FUNCTION update_forum_timestamp();

DROP TRIGGER IF EXISTS trigger_forum_comments_updated ON forum_comments;
CREATE TRIGGER trigger_forum_comments_updated
    BEFORE UPDATE ON forum_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_forum_timestamp();

-- ============================================================
-- 4. Enable RLS
-- ============================================================

ALTER TABLE forum_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE forum_post_tags ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 5. Create RLS Policies
-- ============================================================

-- Posts Policies
DROP POLICY IF EXISTS "Anyone can view posts" ON forum_posts;
CREATE POLICY "Anyone can view posts"
    ON forum_posts FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Authenticated users can create posts" ON forum_posts;
CREATE POLICY "Authenticated users can create posts"
    ON forum_posts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own posts" ON forum_posts;
CREATE POLICY "Users can update their own posts"
    ON forum_posts FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own posts" ON forum_posts;
CREATE POLICY "Users can delete their own posts"
    ON forum_posts FOR DELETE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role can manage posts" ON forum_posts;
CREATE POLICY "Service role can manage posts"
    ON forum_posts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments Policies
DROP POLICY IF EXISTS "Anyone can view comments" ON forum_comments;
CREATE POLICY "Anyone can view comments"
    ON forum_comments FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Authenticated users can create comments" ON forum_comments;
CREATE POLICY "Authenticated users can create comments"
    ON forum_comments FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own comments" ON forum_comments;
CREATE POLICY "Users can update their own comments"
    ON forum_comments FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own comments" ON forum_comments;
CREATE POLICY "Users can delete their own comments"
    ON forum_comments FOR DELETE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role can manage comments" ON forum_comments;
CREATE POLICY "Service role can manage comments"
    ON forum_comments FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Tags Policies
DROP POLICY IF EXISTS "Anyone can view tags" ON forum_tags;
CREATE POLICY "Anyone can view tags"
    ON forum_tags FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Service role can manage tags" ON forum_tags;
CREATE POLICY "Service role can manage tags"
    ON forum_tags FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Post Tags Policies
DROP POLICY IF EXISTS "Anyone can view post tags" ON forum_post_tags;
CREATE POLICY "Anyone can view post tags"
    ON forum_post_tags FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Service role can manage post tags" ON forum_post_tags;
CREATE POLICY "Service role can manage post tags"
    ON forum_post_tags FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- 6. Insert Default Tags
-- ============================================================

INSERT INTO forum_tags (name, description, color) VALUES
    ('General', 'General discussions', '#D4AF37'),
    ('Dating', 'Dating advice and experiences', '#FF6B6B'),
    ('Social Skills', 'Improving social interactions', '#4ECDC4'),
    ('Confidence', 'Building self-confidence', '#95E1D3'),
    ('Relationships', 'Relationship advice', '#F38181'),
    ('Success Stories', 'Share your wins', '#4CAF50'),
    ('Questions', 'Ask the community', '#2196F3'),
    ('Inner Game', 'Mindset and mental models', '#9C27B0')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 7. Create Sample Posts (OPTIONAL - Comment out if not needed)
-- ============================================================
-- NOTE: Replace 'YOUR_USER_ID' with your actual user ID from auth.users table
-- To find your ID: SELECT id FROM auth.users LIMIT 1;

-- Uncomment these lines and replace YOUR_USER_ID to create sample posts:
/*
DO $$
DECLARE
    admin_user_id UUID;
    post1_id UUID;
    post2_id UUID;
    general_tag_id UUID;
    questions_tag_id UUID;
BEGIN
    -- Get the first user (change this to your admin user ID)
    SELECT id INTO admin_user_id FROM auth.users LIMIT 1;

    -- Get tag IDs
    SELECT id INTO general_tag_id FROM forum_tags WHERE name = 'General';
    SELECT id INTO questions_tag_id FROM forum_tags WHERE name = 'Questions';

    -- Create welcome post
    INSERT INTO forum_posts (user_id, title, content, is_pinned, views, likes)
    VALUES (
        admin_user_id,
        '🎉 Welcome to the PathForge Community!',
        E'Hey everyone! 👋\n\nWelcome to our community forum. This is a place where we can:\n\n• Share experiences and insights\n• Ask questions and get advice\n• Celebrate wins and successes\n• Support each other on our journeys\n\nFeel free to introduce yourself and start conversations. Let''s grow together!\n\n- The PathForge Team',
        true,
        42,
        15
    )
    RETURNING id INTO post1_id;

    -- Tag the welcome post
    INSERT INTO forum_post_tags (post_id, tag_id) VALUES (post1_id, general_tag_id);

    -- Create example question post
    INSERT INTO forum_posts (user_id, title, content, views, likes)
    VALUES (
        admin_user_id,
        'How do you handle nervousness in social situations?',
        E'I''ve been working on my social skills and one thing I still struggle with is nervousness when meeting new people.\n\nWhat techniques have worked for you? I''d love to hear your experiences!',
        28,
        8
    )
    RETURNING id INTO post2_id;

    -- Tag the question post
    INSERT INTO forum_post_tags (post_id, tag_id) VALUES (post2_id, questions_tag_id);

    -- Add a sample comment to the question
    INSERT INTO forum_comments (post_id, user_id, content, likes)
    VALUES (
        post2_id,
        admin_user_id,
        E'Great question! I find that deep breathing helps a lot. Before any social interaction, I take 3 deep breaths and remind myself that everyone feels nervous sometimes.',
        5
    );

END $$;
*/

-- ============================================================
-- Setup Complete!
-- ============================================================

SELECT 'Forum tables created successfully!' AS status;
SELECT COUNT(*) AS tag_count FROM forum_tags;
-- SELECT COUNT(*) AS post_count FROM forum_posts;  -- Uncomment if you created sample posts