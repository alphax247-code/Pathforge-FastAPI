# Video Chapters Feature - User Guide

## Overview
Your PathForge platform now has YouTube-like chapter functionality for videos! This allows users to easily navigate through different sections of your video content.

## Features Implemented

### 1. **Chapter Markers on Progress Bar**
- Visual markers appear on the video progress bar showing where each chapter begins
- Hover over markers to see chapter titles
- Click markers to jump directly to that chapter

### 2. **Current Chapter Display**
- The current chapter name is displayed next to the video timestamp
- Updates automatically as the video plays

### 3. **Chapters Panel**
- Click the 📑 button in the video controls to open the chapters list
- Shows all chapters with timestamps
- Click any chapter to jump to it
- The active chapter is highlighted in gold

### 4. **Admin Management**
- Easy-to-use interface for adding/editing chapters
- Time format: MM:SS (e.g., 1:30 for 1 minute 30 seconds)
- Chapters are automatically sorted by time

## How to Add Chapters to Videos

### Step 1: Run the SQL Migration
First, add the chapters column to your videos table in Supabase:

```sql
-- Go to Supabase SQL Editor and run:
-- File location: archived_files/sql_schemas/add_chapters_to_videos.sql

ALTER TABLE videos
ADD COLUMN IF NOT EXISTS chapters JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_videos_chapters ON videos USING GIN (chapters);
```

### Step 2: Add Chapters via Admin Panel

You can add chapters in **two ways**:

#### Option A: When Uploading a New Video
1. Go to `/admin/videos` in your PathForge application
2. Fill in the video details (Title, Playlist, Description, etc.)
3. Scroll to the "Video Chapters (Optional)" section
4. Click "+ Add Chapter" to add a new chapter
5. Enter the timestamp in MM:SS format (e.g., `0:00`, `1:30`, `5:15`)
6. Enter a descriptive title for the chapter
7. Click "+ Add Chapter" again to add more chapters
8. Upload your video file and submit the form

#### Option B: Editing an Existing Video
1. Go to `/admin/videos` in your PathForge application
2. Find the video you want to add chapters to
3. Click the "✏️ Edit" button
4. Scroll to the "Video Chapters (Optional)" section
5. Click "+ Add Chapter" to add a new chapter
6. Enter the timestamp in MM:SS format (e.g., `0:00`, `1:30`, `5:15`)
7. Enter a descriptive title for the chapter
8. Click "+ Add Chapter" again to add more chapters
9. Click "Save Changes"

### Example Chapter Structure

For a 10-minute video about social skills:
- `0:00` - Introduction
- `1:30` - The Science of First Impressions
- `4:15` - Body Language Basics
- `7:00` - Conversation Starters
- `9:15` - Summary & Next Steps

## Technical Details

### Database Structure
```json
{
  "chapters": [
    {"time": 0, "title": "Introduction"},
    {"time": 90, "title": "The Science of First Impressions"},
    {"time": 255, "title": "Body Language Basics"}
  ]
}
```

- Stored as JSONB in PostgreSQL
- `time` is in seconds
- Chapters are automatically sorted by time

### API Response
The `/api/lessons` endpoint now includes chapters in the response:
```json
{
  "id": 1,
  "title": "Video Title",
  "chapters": [
    {"time": 0, "title": "Introduction"},
    {"time": 90, "title": "Main Content"}
  ]
}
```

## User Experience

### Desktop
- Hover over chapter markers to see titles
- Click the chapters button (📑) to see the full list
- Click any chapter in the list to jump to it

### Mobile
- Tap chapter markers on the progress bar
- Tap the chapters button to view the list
- Tap chapters in the list to navigate

## Tips for Creating Good Chapters

1. **Start at 0:00**: Always include an introduction chapter at the beginning
2. **Clear Titles**: Use descriptive, concise chapter titles (e.g., "Body Language Basics" not "Part 2")
3. **Logical Breaks**: Place chapters at natural content transitions
4. **Not Too Many**: 5-8 chapters work best for most videos
5. **Not Too Few**: Videos under 5 minutes may not need chapters

## Benefits

- **Better Navigation**: Users can quickly find specific content
- **Increased Engagement**: Users are more likely to watch longer videos when they can skip to relevant sections
- **Professional Look**: Matches the UX of major video platforms like YouTube
- **Improved Learning**: Students can easily review specific topics

## Troubleshooting

### Chapters not appearing?
1. Make sure you've run the SQL migration
2. Check that chapters are saved in the database (use Supabase dashboard)
3. Verify the video metadata includes the chapters field

### Chapter markers in wrong position?
- Check that your time values are in seconds in the database
- Ensure times are sorted in ascending order

### Can't add chapters in admin panel?
- Make sure you're logged in as an admin
- Check browser console for JavaScript errors
- Verify CSRF token is valid
