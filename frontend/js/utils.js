/**
 * js/utils.js
 *
 * A collection of small, reusable utility functions
 * to keep our main HTML files and components clean.
 */

/**
 * Gets a specific query parameter from the current URL.
 * For example, on 'project.html?id=5', getQueryParam('id') returns '5'.
 *
 * @param {string} name - The name of the query parameter to find.
 * @returns {string | null} The value of the parameter, or null if not found.
 */
function getQueryParam(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

/**
 * Formats an ISO 8601 timestamp (which the DB provides)
 * into a more human-readable format.
 * Example: "2025-10-30T14:30:00" becomes "Oct 30, 2025, 2:30 PM"
 *
 * @param {string} isoString - The ISO string from the database.
 * @returns {string} A formatted, readable date/time string.
 */
function formatDateTime(isoString) {
    if (!isoString) {
        return 'N/A';
    }
    
    try {
        const date = new Date(isoString);
        
        // Check if the date is valid
        if (isNaN(date.getTime())) {
            return 'Invalid Date';
        }

        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true, // Use AM/PM
        };
        return date.toLocaleString(undefined, options);
    } catch (error) {
        console.error('Error formatting date:', error);
        return isoString; // Return original string on error
    }
}

/**
 * Formats a date string (YYYY-MM-DD) into a readable format.
 * Example: "2025-11-20" becomes "Nov 20, 2025"
 *
 * @param {string} dateString - The date string (e.g., from a 'due_date' field).
 * @returns {string} A formatted, readable date string.
 */
function formatDate(dateString) {
    if (!dateString) {
        return 'N/A';
    }

    try {
        // new Date() can handle "YYYY-MM-DD" but adding "T00:00:00"
        // explicitly tells it to use local time, avoiding timezone issues.
        const date = new Date(dateString + 'T00:00:00');
        
        if (isNaN(date.getTime())) {
            return 'Invalid Date';
        }
        
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        };
        return date.toLocaleDateString(undefined, options);
    } catch (error) {
        console.error('Error formatting date:', error);
        return dateString;
    }
}

/**
 * A simple function to capitalize the first letter of a string.
 * Example: "in progress" becomes "In progress"
 *
 * @param {string} s - The string to capitalize.
 * @returns {string} The capitalized string.
 */
function capitalize(s) {
    if (typeof s !== 'string' || s.length === 0) {
        return '';
    }
    return s.charAt(0).toUpperCase() + s.slice(1);
}