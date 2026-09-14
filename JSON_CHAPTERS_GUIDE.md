# JSON Chapter Management Guide

## Overview
Manage video chapters in bulk using JSON files! This is perfect for:
- Adding chapters to multiple videos at once
- Version controlling your chapter configurations
- Sharing chapter templates across teams
- Backing up chapter data
- Editing chapters in your favorite text editor

## 📥 Import Chapters from JSON

### Step 1: Create Your JSON File

Use this simple format:
```json
{
  "video1.mp4": [
    {"time": 0, "title": "Introduction"},
    {"time": 90, "title": "Main Content"},
    {"time": 300, "title": "Advanced Tips"}
  ],
  "video2.mp4": [
    {"time": 0, "title": "Getting Started"},
    {"time": 120, "title": "Deep Dive"}
  ]
}
```

**Format Rules:**
- **Keys**: Video filename (exactly as stored in Supabase)
- **Values**: Array of chapter objects
- **time**: Integer (seconds from start)
- **title**: String (chapter name)

### Step 2: Import via Admin Panel

1. Go to `/admin/videos`
2. Find the "📂 Bulk Chapter Management (JSON)" section at the top
3. Click "Upload JSON File" in the Import section
4. Select your JSON file
5. Click "Import Chapters"
6. ✅ Success! Chapters are now added to your videos

### Example JSON Files

#### Example 1: Social Skills Course
```json
{
  "introduction_to_social_skills.mp4": [
    {"time": 0, "title": "Course Overview"},
    {"time": 45, "title": "Why Social Skills Matter"},
    {"time": 120, "title": "Course Structure"},
    {"time": 180, "title": "Getting Started"}
  ],
  "body_language_basics.mp4": [
    {"time": 0, "title": "Introduction"},
    {"time": 60, "title": "Posture & Stance"},
    {"time": 180, "title": "Hand Gestures"},
    {"time": 300, "title": "Facial Expressions"},
    {"time": 450, "title": "Personal Space"},
    {"time": 600, "title": "Practice Exercises"}
  ],
  "eye_contact_mastery.mp4": [
    {"time": 0, "title": "The Power of Eye Contact"},
    {"time": 90, "title": "Cultural Differences"},
    {"time": 210, "title": "The 50/70 Rule"},
    {"time": 360, "title": "Common Mistakes"},
    {"time": 480, "title": "Practice Drills"}
  ]
}
```

#### Example 2: Quick Course Updates
```json
{
  "lesson_01.mp4": [
    {"time": 0, "title": "Intro"},
    {"time": 120, "title": "Theory"},
    {"time": 480, "title": "Practice"}
  ],
  "lesson_02.mp4": [
    {"time": 0, "title": "Recap"},
    {"time": 90, "title": "New Concepts"},
    {"time": 360, "title": "Examples"}
  ]
}
```

## 📤 Export Chapters to JSON

### Export All Current Chapters

1. Go to `/admin/videos`
2. Find the "📂 Bulk Chapter Management (JSON)" section
3. Click "📥 Export All Chapters to JSON" in the Export section
4. A JSON file will download automatically
5. Filename format: `video-chapters-YYYY-MM-DD.json`

### What Gets Exported?

- **Only videos with chapters** are included
- Chapters are in the same format used for import
- Perfect for backup or editing

### Edit & Re-import Workflow

1. Export current chapters
2. Edit the JSON file in your text editor
3. Add new videos or modify existing chapters
4. Re-import to update all videos at once

## 🎯 Use Cases

### Use Case 1: Bulk Adding Chapters
You have 20 videos without chapters:

1. Download example JSON
2. Copy the structure for each video filename
3. Add chapter timestamps and titles
4. Import once → All 20 videos updated!

### Use Case 2: Standardized Templates
Create chapter templates for different content types:

**Template: Interview Format**
```json
{
  "FILENAME.mp4": [
    {"time": 0, "title": "Guest Introduction"},
    {"time": 120, "title": "Background Story"},
    {"time": 480, "title": "Key Insights"},
    {"time": 900, "title": "Q&A Session"},
    {"time": 1500, "title": "Closing Thoughts"}
  ]
}
```

**Template: Tutorial Format**
```json
{
  "FILENAME.mp4": [
    {"time": 0, "title": "What You'll Learn"},
    {"time": 60, "title": "Prerequisites"},
    {"time": 180, "title": "Step-by-Step Guide"},
    {"time": 720, "title": "Common Mistakes"},
    {"time": 900, "title": "Summary & Resources"}
  ]
}
```

### Use Case 3: Version Control
Keep your chapters in Git:

```bash
# Save chapters
git add video-chapters.json
git commit -m "Add chapters for social skills module"

# Track changes over time
git log video-chapters.json

# Revert if needed
git checkout HEAD~1 video-chapters.json
```

### Use Case 4: Team Collaboration
Content creator workflow:

1. **Creator**: Makes videos, exports chapters template
2. **Editor**: Fills in chapter times after editing
3. **QA**: Reviews and adjusts chapter titles
4. **Admin**: Imports final version to platform

## ⚠️ Important Notes

### Filename Matching
- Filenames must **exactly match** what's in your database
- Case-sensitive!
- Include file extension (e.g., `.mp4`)
- Check your Supabase `videos` table for exact filenames

### Time Format
- Always use **seconds** (not MM:SS) in JSON
- `90` = 1 minute 30 seconds
- `300` = 5 minutes
- `3600` = 1 hour

### Validation
The import process validates:
- ✅ JSON syntax is correct
- ✅ Video files exist in database
- ✅ Chapter format is valid
- ✅ Times are integers
- ✅ Titles are strings

If errors occur, you'll see:
- Number of videos updated successfully
- List of errors for videos that failed

## 🔧 Troubleshooting

### "Video not found" Error
**Problem**: Filename in JSON doesn't match database

**Solution**:
1. Go to `/admin/videos`
2. Check exact filename in the video list
3. Update JSON to match exactly

### "Invalid JSON" Error
**Problem**: JSON syntax error

**Solution**:
1. Use a JSON validator (jsonlint.com)
2. Check for:
   - Missing commas
   - Extra commas
   - Unclosed brackets
   - Unquoted strings

### Import Shows 0 Updated
**Problem**: No videos matched or all had errors

**Solution**:
1. Check browser console for detailed errors
2. Verify filenames match exactly
3. Ensure JSON format is correct

## 💡 Pro Tips

### Tip 1: Start with Export
If you have existing chapters, export first to see the exact format and filenames.

### Tip 2: Test with One Video
Before importing 50 videos, test with just one:
```json
{
  "test-video.mp4": [
    {"time": 0, "title": "Test Chapter"}
  ]
}
```

### Tip 3: Use a JSON Editor
VSCode, Sublime, or online editors provide:
- Syntax highlighting
- Auto-formatting
- Error detection

### Tip 4: Keep Backups
Before re-importing, export current chapters as backup.

### Tip 5: Time Conversion Helper
Quick conversion reference:
- 30 seconds = `30`
- 1 minute = `60`
- 1.5 minutes = `90`
- 5 minutes = `300`
- 10 minutes = `600`
- 30 minutes = `1800`

Or use: `(minutes * 60) + seconds`

## 📋 Quick Reference

### Valid JSON Structure
```json
{
  "filename.mp4": [
    {"time": 0, "title": "Chapter 1"},
    {"time": 120, "title": "Chapter 2"}
  ]
}
```

### Invalid Examples

❌ **Wrong - Time as string**
```json
{"time": "1:30", "title": "Chapter"}
```

❌ **Wrong - Missing required fields**
```json
{"title": "Chapter"}
```

❌ **Wrong - Not an array**
```json
{"filename.mp4": {"time": 0, "title": "Chapter"}}
```

✅ **Correct**
```json
{"filename.mp4": [{"time": 90, "title": "Chapter"}]}
```

## 🚀 Advanced: Scripting

### Generate JSON from CSV
If you have chapters in a spreadsheet:

```python
import csv
import json

# Read CSV: filename, time, title
chapters = {}
with open('chapters.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        filename = row['filename']
        if filename not in chapters:
            chapters[filename] = []
        chapters[filename].append({
            'time': int(row['time']),
            'title': row['title']
        })

# Write JSON
with open('chapters.json', 'w') as f:
    json.dump(chapters, f, indent=2)
```

### Auto-generate Chapter Template
```python
import json

# Generate chapters every 2 minutes for a 10-minute video
chapters = {
    "my-video.mp4": [
        {"time": i * 120, "title": f"Section {i+1}"}
        for i in range(5)
    ]
}

with open('template.json', 'w') as f:
    json.dump(chapters, f, indent=2)
```

---

**Ready to manage chapters at scale!** 🎉

For the visual UI method, see `VIDEO_CHAPTERS_GUIDE.md`
