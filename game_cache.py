"""
Game questions cache for faster loading
"""
import random
import requests
from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

class GameQuestionsCache:
    """Cache for game questions to speed up API responses"""

    def __init__(self):
        self.questions = {}
        self.last_refresh = None
        self.cache_duration = 300  # 5 minutes

    def load_all_questions(self):
        """Load all game questions into memory"""
        print("Loading game questions into cache...")

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        }

        try:
            # Fetch all active questions at once
            url = f"{SUPABASE_URL}/rest/v1/game_questions?is_active=eq.true&select=*"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                all_questions = response.json()

                # Organize by game type and difficulty
                self.questions = {
                    'attachment': {'easy': [], 'normal': [], 'hard': []},
                    'cognitive_distortions': {'easy': [], 'normal': [], 'hard': []},
                    'communication_styles': {'easy': [], 'normal': [], 'hard': []},
                    'love_languages': {'easy': [], 'normal': [], 'hard': []}
                }

                for q in all_questions:
                    game_type = q['game_type']
                    difficulty = q.get('difficulty', 'easy')

                    if game_type in self.questions and difficulty in self.questions[game_type]:
                        self.questions[game_type][difficulty].append(q)

                print(f"Cached {len(all_questions)} questions")

                # Print breakdown
                for game_type in self.questions:
                    total = sum(len(self.questions[game_type][diff]) for diff in ['easy', 'normal', 'hard'])
                    print(f"  {game_type}: {total} questions")

                import time
                self.last_refresh = time.time()
                return True

            else:
                print(f"Failed to load questions: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error loading questions cache: {e}")
            return False

    def get_random_question(self, game_type, difficulty='easy', exclude_ids=None):
        """Get a random question from cache"""

        # Check if cache needs refresh
        if not self.questions or not self.last_refresh:
            self.load_all_questions()
        else:
            import time
            if time.time() - self.last_refresh > self.cache_duration:
                self.load_all_questions()

        # Get questions for this game type and difficulty
        if game_type not in self.questions:
            return None

        available_questions = self.questions[game_type].get(difficulty, [])

        # Try fallback to any difficulty if none found
        if not available_questions:
            for diff in ['easy', 'normal', 'hard']:
                available_questions = self.questions[game_type].get(diff, [])
                if available_questions:
                    break

        if not available_questions:
            return None

        # Filter out excluded questions
        if exclude_ids:
            available_questions = [q for q in available_questions if q['id'] not in exclude_ids]

        if not available_questions:
            # If all questions excluded, use any question
            available_questions = []
            for diff in ['easy', 'normal', 'hard']:
                available_questions.extend(self.questions[game_type].get(diff, []))

        if not available_questions:
            return None

        # Return random question
        return random.choice(available_questions)

# Global cache instance
game_cache = GameQuestionsCache()
