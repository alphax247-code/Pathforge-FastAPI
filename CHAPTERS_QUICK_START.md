# Video Chapters - Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Run SQL Migration (One-time setup)
```sql
-- In Supabase SQL Editor, run:
ALTER TABLE videos ADD COLUMN IF NOT EXISTS chapters JSONB DEFAULT '[]'::jsonb;
CREATE INDEX IF NOT EXISTS idx_videos_chapters ON videos USING GIN (chapters);
```

### Step 2: Choose Your Method

#### Method A: JSON (Bulk - Recommended for Multiple Videos)
1. Go to `/admin/videos`
2. Download example JSON template
3. Edit the JSON file with your chapters
4. Upload and import - Done! 🎉

**Example JSON:**
```json
{
  "my_video.mp4": [
    {"time": 0, "title": "Introduction"},
    {"time": 120, "title": "Main Content"},
    {"time": 480, "title": "Summary"}
  ]
}
```

#### Method B: Admin UI (Individual Videos)
1. Go to `/admin/videos`
2. Click "Upload New Video" or "✏️ Edit" existing video
3. Find "Video Chapters (Optional)" section
4. Click "+ Add Chapter"
5. Enter time (MM:SS format) and title
6. Save - Done! 🎉

### Step 3: View Results
1. Go to `/lessons`
2. Click any video with chapters
3. See chapter markers, current chapter display, and chapter list!

## 📊 Comparison: JSON vs UI

| Feature | JSON Method | UI Method |
|---------|-------------|-----------|
| **Best For** | Multiple videos | Single videos |
| **Speed** | Very fast (bulk) | Slower (one-by-one) |
| **Version Control** | Yes (Git-friendly) | No |
| **Offline Editing** | Yes | No |
| **Learning Curve** | Medium | Easy |
| **Backup/Export** | Built-in | Manual |

## 💡 Quick Tips

### Time Conversion Cheat Sheet
- `30` = 30 seconds
- `60` = 1 minute
- `90` = 1 minute 30 seconds
- `120` = 2 minutes
- `300` = 5 minutes
- `600` = 10 minutes
- `900` = 15 minutes
- `1800` = 30 minutes

### Best Practices
1. ✅ Always start with 0:00 for introduction
2. ✅ Use clear, descriptive titles
3. ✅ 5-8 chapters works best
4. ✅ Place chapters at natural breaks
5. ✅ Test with one video first

## 🎯 Common Workflows

### Workflow 1: New Course (20 videos)
1. Create JSON file with all 20 videos
2. Add chapter templates for each
3. Import once → All done!

### Workflow 2: Update Existing Video
1. Go to `/admin/videos`
2. Click "✏️ Edit" on video
3. Modify chapters
4. Save

### Workflow 3: Backup & Share
1. Export all chapters as JSON
2. Commit to Git
3. Share with team
4. They can import on their instance

## 📚 Documentation Files

- **CHAPTER_FEATURE_SUMMARY.md** - Complete overview
- **VIDEO_CHAPTERS_GUIDE.md** - UI method detailed guide
- **JSON_CHAPTERS_GUIDE.md** - JSON method detailed guide
- **CHAPTERS_QUICK_START.md** - This file!

## ❓ Troubleshooting

**Problem**: Chapters not showing
- **Solution**: Make sure SQL migration ran successfully

**Problem**: Import says "Video not found"
- **Solution**: Check filename matches exactly (case-sensitive!)

**Problem**: Time format error in UI
- **Solution**: Use MM:SS format (e.g., 1:30, not 90)

**Problem**: Invalid JSON error
- **Solution**: Validate JSON at jsonlint.com

## 🎉 You're Ready!

Pick your method and start adding chapters to your videos. Users will love the YouTube-like navigation!

---

**Need Help?**
- Full UI Guide: `VIDEO_CHAPTERS_GUIDE.md`
- Full JSON Guide: `JSON_CHAPTERS_GUIDE.md`
- Technical Details: `CHAPTER_FEATURE_SUMMARY.md`
