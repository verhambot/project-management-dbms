/**
 * js/auth.js
 *
 * This file handles all client-side authentication logic:
 * 1. Saving the JWT token on login.
 * 2. Retrieving the JWT token for API calls.
 * 3. Clearing the JWT token on logout.
 * 4. Protecting pages by redirecting unauthenticated users.
 */

// We use a constant for the key in localStorage for consistency
const TOKEN_KEY = 'access_token';

/**
 * Saves the access token to localStorage.
 * @param {string} token - The JWT access token received from the API.
 */
function saveToken(token) {
    if (!token) {
        console.error('No token provided to saveToken');
        return;
    }
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Retrieves the access token from localStorage.
 * @returns {string | null} The stored token, or null if it doesn't exist.
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Clears the access token from localStorage.
 */
function logout() {
    localStorage.removeItem(TOKEN_KEY);
    // After logging out, always redirect to the login page
    window.location.href = 'index.html';
}

/**
 * Checks if a user is currently logged in (i.e., has a token).
 * @returns {boolean} True if a token exists, false otherwise.
 */
function isLoggedIn() {
    return !!getToken();
}

/**
 * This is the "page guard" function.
 * You must call this function at the top of any page that
 * requires a user to be logged in (e.g., dashboard.html, project.html).
 *
 * It checks for a token and redirects to the login page if one isn't found.
 */
function protectPage() {
    if (!isLoggedIn()) {
        console.warn('Access denied. No token found. Redirecting to login.');
        // We use replace() so the user can't click "back" to the protected page.
        window.location.replace('index.html');
    }
}

/**
 * A helper function to get the user's ID from the token.
 * JWT tokens are three parts: header.payload.signature
 * The payload is Base64-encoded JSON.
 * * @returns {number | null} The user_id, or null if token is invalid/missing.
 */
function getUserIdFromToken() {
    const token = getToken();
    if (!token) {
        return null;
    }

    try {
        // Get the payload (the middle part of the token)
        const payloadBase64 = token.split('.')[1];
        // Decode the Base64 string
        const payloadJson = atob(payloadBase64);
        // Parse the JSON string into an object
        const payload = JSON.parse(payloadJson);

        // 'user_id' is what you defined in your auth.py's create_access_token
        return payload.user_id || null; 
        
    } catch (error) {
        console.error('Error decoding token:', error);
        // This can happen if the token is malformed or expired
        return null;
    }
}