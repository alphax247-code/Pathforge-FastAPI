// PathForge - Backend-Connected JavaScript File
// This version connects to Flask backend API instead of using localStorage
// All data is now stored in the database

// ============================================================================
// API CONFIGURATION
// ============================================================================

const API_BASE_URL = '';  // Empty means same domain, change if backend is on different domain
const API_ENDPOINTS = {
    progress: '/api/progress',
    addXP: '/api/add-xp',
    completeDirective: '/api/daily-directive/complete',
    unlockAchievement: '/api/achievements/unlock',
    resetProgress: '/api/reset-progress',
    completeOnboarding: '/api/onboarding/complete'
};

// ============================================================================
// API HELPER FUNCTIONS
// ============================================================================

/**
 * Make API request with error handling
 * @param {string} endpoint - API endpoint
 * @param {object} options - Fetch options
 * @returns {Promise} Response data
 */
async function apiRequest(endpoint, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'same-origin'  // Include cookies for session
    };

    try {
        const response = await fetch(API_BASE_URL + endpoint, {
            ...defaultOptions,
            ...options
        });

        if (response.status === 401) {
            // Not authenticated - only redirect if we're NOT on a public page
            const publicPages = ['/welcome', '/', '/login', '/signup'];
            const currentPath = window.location.pathname;
            const isPublicPage = publicPages.some(page => currentPath === page || currentPath.includes('welcome'));

            if (!isPublicPage) {
                showNotification('Please log in to continue');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 1500);
            }
            return null;
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Request failed');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        // Only show notification on non-public pages
        const publicPages = ['/welcome', '/', '/login', '/signup'];
        const currentPath = window.location.pathname;
        const isPublicPage = publicPages.some(page => currentPath === page || currentPath.includes('welcome'));

        if (!isPublicPage) {
            showNotification('Error: ' + error.message);
        }
        throw error;
    }
}

/**
 * Get data from API (GET request)
 */
async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: 'GET' });
}

/**
 * Send data to API (POST request)
 */
async function apiPost(endpoint, data) {
    return apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

// ============================================================================
// INITIALIZATION & SETUP
// ============================================================================

document.addEventListener('DOMContentLoaded', async function() {
    console.log('PathForge Backend-Connected initialized');

    // Add notification container if it doesn't exist
    if (!document.getElementById('notification')) {
        const notif = document.createElement('div');
        notif.id = 'notification';
        document.body.appendChild(notif);
    }

    // Check if we're on a public page that doesn't require authentication
    const publicPages = ['/welcome', '/', '/login', '/signup'];
    const currentPath = window.location.pathname;
    const isPublicPage = publicPages.some(page => currentPath === page || currentPath.includes('welcome'));

    // Only load user data and set up auto-refresh on authenticated pages
    if (!isPublicPage) {
        // Load user data from backend API
        await loadUserData();

        // Set up any dynamic content
        updateProgressBars();

        // Auto-refresh progress every 30 seconds
        setInterval(loadUserData, 30000);
    }

    // Add smooth entrance on page load for welcome page
    if (document.body.classList.contains('welcome-page') || currentPath.includes('welcome')) {
        document.body.style.opacity = '1';
    }
});

// ============================================================================
// NAVIGATION FUNCTIONS
// ============================================================================

function goTo(page) {
    const pageMap = {
        'lessons': '/lessons',
        'text-practice': '/text-practice',
        'missions': '/missions',
        'inner-game': '/inner-game',
        'daily-directive': '/daily-directive',
        'social-challenge': '/missions',
        'speech-practice': '/speech-practice',
        'profile': '/profile',
        'practice-session': '/speech-practice',
        'dashboard': '/dashboard',
        'index': '/index'
    };
    
    const url = pageMap[page] || '/dashboard';
    window.location.href = url;
}

// Welcome page navigation with fade effect
function startJourney() {
    // Fade out animation before navigation
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.5s ease-out';

    setTimeout(() => {
        window.location.href = '/login';
    }, 500);
}

// ============================================================================
// NOTIFICATION SYSTEM
// ============================================================================

function showNotification(message, duration = 3000) {
    let notification = document.getElementById('notification');
    
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        document.body.appendChild(notification);
    }
    
    notification.textContent = message;
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, duration);
}

// ============================================================================
// USER DATA & PROGRESS MANAGEMENT (Backend-Connected)
// ============================================================================

/**
 * Load user data from backend API
 * Replaces localStorage.getItem()
 */
async function loadUserData() {
    try {
        const data = await apiGet(API_ENDPOINTS.progress);
        
        if (!data) return; // Not authenticated or error
        
        // Update streak displays
        const streakDisplays = document.querySelectorAll('.streak-number, .stat-value');
        streakDisplays.forEach(display => {
            if (display.parentElement && display.parentElement.textContent.includes('Streak')) {
                display.textContent = data.streak;
            }
        });
        
        // Update XP displays
        const xpDisplays = document.querySelectorAll('.xp-value, .stat-value');
        xpDisplays.forEach(display => {
            if (display.parentElement && display.parentElement.textContent.includes('XP')) {
                display.textContent = data.xp;
            }
        });
        
        // Update level displays
        const levelDisplays = document.querySelectorAll('.level-value, .stat-value');
        levelDisplays.forEach(display => {
            if (display.parentElement && display.parentElement.textContent.includes('Level')) {
                display.textContent = data.level;
            }
        });
        
        // Store in memory for quick access (not localStorage)
        window.userData = data;
        
        // Update progress bar if exists
        updateProgressBar(data.xp, data.level);
        
        console.log('User data loaded from backend:', data);
        return data;
    } catch (error) {
        console.error('Failed to load user data:', error);
        return null;
    }
}

/**
 * Save progress to backend
 * Replaces localStorage.setItem()
 */
async function saveProgress(type, value) {
    try {
        const data = { [type]: value };
        const result = await apiPost(API_ENDPOINTS.progress, data);
        
        if (result && result.success) {
            showNotification('Progress saved!', 2000);
            // Reload data to get updated values
            await loadUserData();
        }
    } catch (error) {
        console.error('Failed to save progress:', error);
    }
}

/**
 * Update progress bars with animation
 */
function updateProgressBars() {
    const progressBars = document.querySelectorAll('.progress-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = width;
        }, 100);
    });
}

/**
 * Update XP progress bar
 */
function updateProgressBar(xp, level) {
    // Update progress fill bar (for linear progress bars)
    const progressBar = document.querySelector('.progress-fill');
    if (progressBar) {
        const xpNeeded = level * 500;  // Must match backend formula
        const xpInLevel = xp % xpNeeded;
        const percentage = (xpInLevel / xpNeeded) * 100;

        progressBar.style.width = percentage + '%';

        // Update text if exists
        const progressText = document.querySelector('.progress-text');
        if (progressText) {
            progressText.textContent = `${xpInLevel} / ${xpNeeded} XP to next level`;
        }
    }

    // Update circular progress bar (for SVG circle progress)
    const progressCircle = document.querySelector('.progress-fill-circle');
    const progressTextNew = document.querySelector('.progress-text-new');

    if (progressCircle && progressTextNew) {
        const xpNeeded = level * 500;  // Must match backend formula
        const xpInLevel = xp % xpNeeded;
        const percentage = Math.round((xpInLevel / xpNeeded) * 100);

        // Calculate stroke-dashoffset (314 is full circle, 0 is complete)
        const circumference = 314;
        const offset = circumference - (circumference * percentage / 100);

        progressCircle.style.strokeDashoffset = offset;
        progressTextNew.textContent = percentage + '%';
    }
}

// ============================================================================
// XP & LEVEL MANAGEMENT (Backend-Connected)
// ============================================================================

/**
 * Add XP to user - calls backend API
 * Replaces localStorage XP management
 */
async function addXP(amount) {
    try {
        const result = await apiPost(API_ENDPOINTS.addXP, { amount });
        
        if (result && result.success) {
            showNotification(`+${amount} XP earned!`);
            
            // Check for level up
            if (result.leveled_up) {
                showNotification(`🎉 Level Up! You are now level ${result.level}!`, 4000);
                playLevelUpAnimation();
            }
            
            // Update display
            await loadUserData();
            return result;
        }
    } catch (error) {
        console.error('Failed to add XP:', error);
    }
}

/**
 * Check level up status
 */
function checkLevelUp() {
    // This is now handled by the backend
    // Just reload user data to get updated level
    loadUserData();
}

/**
 * Play level up animation (customize as needed)
 */
function playLevelUpAnimation() {
    // Add your level up animation here
    console.log('Level up animation!');
    // Example: flash the screen, show confetti, etc.
}

// ============================================================================
// INNER GAME FUNCTIONS (Backend-Connected)
// ============================================================================

async function startExercise(exerciseName) {
    showNotification('Loading ' + exerciseName + ' exercise...');
    console.log('Starting exercise:', exerciseName);
    
    // You can save this to backend if needed
    await saveProgress('currentExercise', exerciseName);
    
    setTimeout(() => {
        showNotification('Exercise module coming soon!');
    }, 1500);
}

function openJournal() {
    showNotification('Opening reflection journal...');
    console.log('Opening journal');
    
    setTimeout(() => {
        showNotification('Journal feature coming soon!');
    }, 1500);
}

// ============================================================================
// DAILY DIRECTIVE FUNCTIONS (Backend-Connected)
// ============================================================================

/**
 * Complete daily directive - calls backend API
 */
async function completeDirective() {
    try {
        const result = await apiPost(API_ENDPOINTS.completeDirective, {});
        
        if (result && result.success) {
            showNotification(`Congratulations! +${result.xp_awarded} XP earned!`, 3000);
            
            // Update streak display
            const streakElement = document.querySelector('.streak-number');
            if (streakElement) {
                streakElement.textContent = result.streak;
            }
            
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to complete directive:', error);
        if (error.message.includes('Already completed')) {
            showNotification('You already completed today\'s challenge!');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        }
    }
}

function skipDirective() {
    if (confirm('Are you sure you want to skip today\'s challenge?')) {
        showNotification('Challenge skipped. Come back tomorrow!');
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 1500);
    }
}

// ============================================================================
// ACHIEVEMENT SYSTEM (Backend-Connected)
// ============================================================================

/**
 * Unlock achievement - calls backend API
 */
async function unlockAchievement(achievementId) {
    try {
        const result = await apiPost(API_ENDPOINTS.unlockAchievement, { achievement_id: achievementId });
        
        if (result && result.success) {
            if (result.new_achievement) {
                showNotification('🏆 Achievement Unlocked!', 3000);
                playAchievementAnimation(achievementId);
            } else {
                console.log('Achievement already unlocked');
            }
        }
    } catch (error) {
        console.error('Failed to unlock achievement:', error);
    }
}

function playAchievementAnimation(achievementId) {
    // Add your achievement animation here
    console.log('Achievement unlocked:', achievementId);
}

// ============================================================================
// LESSON FUNCTIONS (Backend-Connected)
// ============================================================================

async function startLesson(lessonId) {
    showNotification('Loading lesson...');
    console.log('Starting lesson:', lessonId);
    
    // Save current lesson
    await saveProgress('currentLesson', lessonId);
}

async function completeLesson(lessonId) {
    try {
        await saveProgress('completed_lesson', lessonId);
        await addXP(50);  // Award XP for completing lesson
        showNotification('Lesson completed! +50 XP');
    } catch (error) {
        console.error('Failed to complete lesson:', error);
    }
}

// ============================================================================
// PROFILE FUNCTIONS
// ============================================================================

function editSetting(settingName) {
    showNotification('Opening ' + settingName + ' settings...');
    console.log('Edit setting:', settingName);
}

function logout() {
    if (confirm('Are you sure you want to log out?')) {
        showNotification('Logging out...');
        setTimeout(() => {
            window.location.href = '/logout';
        }, 1000);
    }
}

function deleteAccount() {
    const confirmation = prompt('Type "DELETE" to confirm account deletion:');
    if (confirmation === 'DELETE') {
        showNotification('Account deletion initiated...');
        setTimeout(() => {
            alert('Account deleted. We\'re sorry to see you go!');
            window.location.href = '/logout';
        }, 1500);
    }
}

// ============================================================================
// PRACTICE SESSION FUNCTIONS
// ============================================================================

function endPractice() {
    if (confirm('Are you sure you want to end this practice session?')) {
        // You could save practice stats here
        showNotification('Practice session ended. Great work!');
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 1000);
    }
}

async function savePracticeResults(results) {
    // Save practice session results to backend
    try {
        await saveProgress('lastPracticeResults', JSON.stringify(results));
        await addXP(results.xp || 25);
    } catch (error) {
        console.error('Failed to save practice results:', error);
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatDate(date) {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Get current user data (from memory, not API call)
 */
function getCurrentUserData() {
    return window.userData || null;
}

/**
 * Refresh user data from backend
 */
async function refreshUserData() {
    return await loadUserData();
}

// ============================================================================
// DEBUG/DEVELOPMENT FUNCTIONS
// ============================================================================

/**
 * Test API connection
 */
async function testAPIConnection() {
    console.log('Testing API connection...');
    try {
        const data = await apiGet(API_ENDPOINTS.progress);
        console.log('API Connection successful!', data);
        showNotification('API Connected! ✅');
        return true;
    } catch (error) {
        console.error('API Connection failed!', error);
        showNotification('API Connection failed! ❌');
        return false;
    }
}

/**
 * Reset progress (for testing only)
 */
async function resetProgress() {
    if (confirm('Are you sure you want to reset all progress? This cannot be undone!')) {
        try {
            const result = await apiPost(API_ENDPOINTS.resetProgress, {});
            if (result && result.success) {
                showNotification('Progress reset!');
                setTimeout(() => {
                    location.reload();
                }, 1500);
            }
        } catch (error) {
            console.error('Failed to reset progress:', error);
        }
    }
}

// ============================================================================
// AUTHENTICATION FUNCTIONS (SIGNUP/LOGIN)
// ============================================================================

/**
 * Go back to previous page
 */
function goBack() {
    window.history.back();
}

/**
 * Handle signup form submission
 */
async function handleSignup(event) {
    event.preventDefault();

    const email = document.getElementById('signupEmailInput').value;
    const password = document.getElementById('signupPasswordInput').value;
    const confirmPassword = document.getElementById('confirmPasswordInput')?.value;
    const errorMessage = document.getElementById('signupErrorMessage');
    const signupBtn = document.getElementById('signupBtn');

    // Clear previous errors
    errorMessage.textContent = '';
    errorMessage.style.display = 'none';

    // Validate passwords match
    if (confirmPassword && password !== confirmPassword) {
        errorMessage.textContent = 'Passwords do not match';
        errorMessage.style.display = 'block';
        return;
    }

    // Validate password strength
    if (password.length < 6) {
        errorMessage.textContent = 'Password must be at least 6 characters';
        errorMessage.style.display = 'block';
        return;
    }

    // Disable button during submission
    signupBtn.disabled = true;
    signupBtn.textContent = 'CREATING ACCOUNT...';

    try {
        // Get CSRF token from hidden input
        const csrfToken = document.getElementById('csrfToken')?.value ||
                         document.getElementById('signupCsrfToken')?.value;

        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                csrf_token: csrfToken,
                username: email.split('@')[0], // Use email prefix as username
                email: email,
                password: password,
                password2: confirmPassword || password
            }),
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Account created successfully!');
            setTimeout(() => {
                window.location.href = data.redirect || '/dashboard';
            }, 1000);
        } else {
            errorMessage.textContent = data.error || 'Signup failed';
            errorMessage.style.display = 'block';
            signupBtn.disabled = false;
            signupBtn.textContent = 'CREATE ACCOUNT';
        }
    } catch (error) {
        console.error('Signup error:', error);
        errorMessage.textContent = 'Network error. Please try again.';
        errorMessage.style.display = 'block';
        signupBtn.disabled = false;
        signupBtn.textContent = 'CREATE ACCOUNT';
    }
}

/**
 * Handle login form submission
 */
async function handleLogin(event) {
    event.preventDefault();

    const email = document.getElementById('emailInput').value;
    const password = document.getElementById('passwordInput').value;
    const errorMessage = document.getElementById('errorMessage');
    const loginBtn = document.getElementById('loginBtn');

    // Clear previous errors
    errorMessage.textContent = '';
    errorMessage.style.display = 'none';

    // Disable button during submission
    loginBtn.disabled = true;
    loginBtn.textContent = 'LOGGING IN...';

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email, // Send full email
                password: password
            }),
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Login successful!');
            setTimeout(() => {
                window.location.href = data.redirect || '/dashboard';
            }, 1000);
        } else {
            errorMessage.textContent = data.error || 'Login failed';
            errorMessage.style.display = 'block';
            loginBtn.disabled = false;
            loginBtn.textContent = 'LOG IN';
        }
    } catch (error) {
        console.error('Login error:', error);
        errorMessage.textContent = 'Network error. Please try again.';
        errorMessage.style.display = 'block';
        loginBtn.disabled = false;
        loginBtn.textContent = 'LOG IN';
    }
}

/**
 * Social signup/login placeholders
 */
function signUpWithGoogle() {
    showNotification('Google signup coming soon!');
    console.log('Google signup clicked');
}

function signUpWithApple() {
    showNotification('Apple signup coming soon!');
    console.log('Apple signup clicked');
}

function signUpWithFacebook() {
    showNotification('Facebook signup coming soon!');
    console.log('Facebook signup clicked');
}

function signInWithGoogle() {
    showNotification('Google login coming soon!');
    console.log('Google login clicked');
}

function signInWithApple() {
    showNotification('Apple login coming soon!');
    console.log('Apple login clicked');
}

function signInWithFacebook() {
    showNotification('Facebook login coming soon!');
    console.log('Facebook login clicked');
}

// ============================================================================
// EXPORT FUNCTIONS TO GLOBAL SCOPE
// ============================================================================

// Make all functions available globally for inline onclick handlers
window.goTo = goTo;
window.startJourney = startJourney;
window.goBack = goBack;
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.signUpWithGoogle = signUpWithGoogle;
window.signUpWithApple = signUpWithApple;
window.signUpWithFacebook = signUpWithFacebook;
window.signInWithGoogle = signInWithGoogle;
window.signInWithApple = signInWithApple;
window.signInWithFacebook = signInWithFacebook;
window.showNotification = showNotification;
window.loadUserData = loadUserData;
window.saveProgress = saveProgress;
window.updateProgressBars = updateProgressBars;
window.updateProgressBar = updateProgressBar;
window.addXP = addXP;
window.checkLevelUp = checkLevelUp;
window.startExercise = startExercise;
window.openJournal = openJournal;
window.completeDirective = completeDirective;
window.skipDirective = skipDirective;
window.unlockAchievement = unlockAchievement;
window.startLesson = startLesson;
window.completeLesson = completeLesson;
window.editSetting = editSetting;
window.logout = logout;
window.deleteAccount = deleteAccount;
window.endPractice = endPractice;
window.savePracticeResults = savePracticeResults;
window.formatDate = formatDate;
window.getCurrentUserData = getCurrentUserData;
window.refreshUserData = refreshUserData;
window.testAPIConnection = testAPIConnection;
window.resetProgress = resetProgress;

// Export API functions for advanced usage
window.apiGet = apiGet;
window.apiPost = apiPost;
window.apiRequest = apiRequest;

// ============================================================================
// ONBOARDING FUNCTIONS
// ============================================================================

let currentStep = 1;
let onboardingData = {
    goals: [],
    experience: '',
    commitment: ''
};

/**
 * Toggle option selection in onboarding
 */
function toggleOption(element) {
    element.classList.toggle('selected');

    // Get the goal text
    const goalText = element.querySelector('h3').textContent;

    // Add or remove from goals array
    const index = onboardingData.goals.indexOf(goalText);
    if (index > -1) {
        onboardingData.goals.splice(index, 1);
    } else {
        onboardingData.goals.push(goalText);
    }
}

/**
 * Select experience level
 */
function selectExperience(element, level) {
    // Remove selected class from all experience cards
    const cards = element.parentElement.querySelectorAll('.option-card');
    cards.forEach(card => card.classList.remove('selected'));

    // Add selected class to clicked card
    element.classList.add('selected');

    // Save experience level
    onboardingData.experience = level;
}

/**
 * Select commitment level
 */
function selectCommitment(element, commitment) {
    // Remove selected class from all commitment cards
    const cards = element.parentElement.querySelectorAll('.option-card');
    cards.forEach(card => card.classList.remove('selected'));

    // Add selected class to clicked card
    element.classList.add('selected');

    // Save commitment level
    onboardingData.commitment = commitment;
}

/**
 * Move to next step in onboarding
 */
function nextStep() {
    // Validate current step
    if (currentStep === 1 && onboardingData.goals.length === 0) {
        showNotification('Please select at least one goal');
        return;
    }
    if (currentStep === 2 && !onboardingData.experience) {
        showNotification('Please select your experience level');
        return;
    }

    // Hide current step
    document.getElementById(`step${currentStep}`).classList.remove('active');

    // Update progress steps
    const steps = document.querySelectorAll('.step');
    steps[currentStep - 1].classList.remove('active');
    steps[currentStep - 1].classList.add('completed');

    // Move to next step
    currentStep++;

    // Show next step
    document.getElementById(`step${currentStep}`).classList.add('active');
    steps[currentStep - 1].classList.add('active');
}

/**
 * Move to previous step in onboarding
 */
function previousStep() {
    // Hide current step
    document.getElementById(`step${currentStep}`).classList.remove('active');

    // Update progress steps
    const steps = document.querySelectorAll('.step');
    steps[currentStep - 1].classList.remove('active');

    // Move to previous step
    currentStep--;

    // Show previous step
    document.getElementById(`step${currentStep}`).classList.add('active');
    steps[currentStep - 1].classList.remove('completed');
    steps[currentStep - 1].classList.add('active');
}

/**
 * Complete onboarding and save preferences
 */
async function completeOnboarding() {
    // Validate final step
    if (!onboardingData.commitment) {
        showNotification('Please select your time commitment');
        return;
    }

    console.log('Onboarding completed:', onboardingData);

    // Save onboarding data to backend using dedicated API endpoint
    try {
        const result = await apiPost(API_ENDPOINTS.completeOnboarding, onboardingData);

        if (result && result.success) {
            showNotification('Welcome to PathForge!');

            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        }
    } catch (error) {
        console.error('Failed to save onboarding data:', error);
        showNotification('Error saving onboarding data');
        // Still redirect to dashboard even if save fails
        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 2000);
    }
}

// Export onboarding functions to global scope
window.toggleOption = toggleOption;
window.selectExperience = selectExperience;
window.selectCommitment = selectCommitment;
window.nextStep = nextStep;
window.previousStep = previousStep;
window.completeOnboarding = completeOnboarding;

console.log('PathForge Backend-Connected JS loaded successfully ✅');
console.log('API Base URL:', API_BASE_URL || 'Same domain');
console.log('Run testAPIConnection() to verify connection');