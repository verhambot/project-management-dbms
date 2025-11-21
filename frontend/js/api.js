/**
 * js/api.js
 *
 * This file is the API client for the entire frontend.
 * It uses functions from auth.js (like getToken) to
 * automatically add the Authorization header to every request.
 */

// The base URL of your FastAPI backend
const API_BASE_URL = 'http://localhost:8000/api';

/**
 * A central wrapper for all JSON-based `fetch` calls.
 * - Sets the correct headers (JSON, Authorization)
 * - Parses the response (or handles errors)
 * - Throws an error for bad responses (e.g., 404, 403, 500)
 *
 * @param {string} endpoint - The API endpoint (e.g., "/projects")
 * @param {object} options - The options for the fetch call (method, body, etc.)
 * @returns {Promise<any>} The JSON response from the API
 */
async function apiFetch(endpoint, options = {}) {
    const { body, ...customOptions } = options;
    const token = getToken(); // From auth.js

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    // Add the auth token if it exists
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Configure the fetch request
    const config = {
        method: options.method || 'GET',
        headers,
        ...customOptions,
    };

    // Add the body for POST/PUT/PATCH requests
    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

        // Check for "No Content" response (for DELETE)
        if (response.status === 204) {
            return null; // Successfully deleted
        }

        // Try to parse the response as JSON
        const data = await response.json();

        if (!response.ok) {
            // If the API returned an error (e.g., 400, 401, 404)
            // 'data.detail' is the standard error format for FastAPI
            const errorMessage = data.detail || `HTTP Error: ${response.status}`;
            throw new Error(errorMessage);
        }

        return data; // Successfully return the JSON data

    } catch (err) {
        console.error('API Fetch Error:', err.message);
        // Re-throw the error so the Alpine.js component can catch it
        throw err;
    }
}

/**
 * A wrapper for file uploads (which use FormData, not JSON).
 *
 * @param {string} endpoint - The API endpoint (e.g., "/attachments/by-issue/1")
 * @param {File} file - The file object from an <input type="file">
 * @param {object} options - Any other fetch options
 * @returns {Promise<any>} The JSON response from the API
 */
async function apiFetchFile(endpoint, file, options = {}) {
    const token = getToken();
    const formData = new FormData();
    formData.append('file', file); // 'file' must match your FastAPI endpoint's File() name

    const config = {
        method: 'POST',
        body: formData,
        headers: {
            ...options.headers,
            // NOTE: We DO NOT set 'Content-Type' here.
            // The browser must set it automatically to 'multipart/form-data'
            // with the correct 'boundary' string.
        },
    };

    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        const data = await response.json();

        if (!response.ok) {
            const errorMessage = data.detail || `HTTP Error: ${response.status}`;
            throw new Error(errorMessage);
        }
        return data;
    } catch (err) {
        console.error('API File Upload Error:', err.message);
        throw err;
    }
}


// --- Create the 'api' object to export all functions ---
const api = {

    // === Authentication ===
    
    /**
     * Logs in a user and saves the token.
     * Note: This one doesn't use apiFetch because it's a special
     * 'application/x-www-form-urlencoded' request.
     */
    async login(username, password) {
        try {
            const params = new URLSearchParams();
            params.append('username', username);
            params.append('password', password);

            const response = await fetch(`${API_BASE_URL}/auth/token`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: params,
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Login failed');
            }

            // On success, save the token (from auth.js)
            saveToken(data.access_token);
            return data;
        } catch (err) {
            console.error('Login Error:', err);
            throw err;
        }
    },

    /**
     * Registers a new user.
     * POST /api/auth/register
     */
    register: (userData) => apiFetch('/auth/register', {
        method: 'POST',
        body: userData, // { username, email, password, ... }
    }),

    /**
     * Gets the current logged-in user's details.
     * GET /api/auth/users/me
     */
    getCurrentUser: () => apiFetch('/auth/users/me'),


    // === Users ===

    /**
     * Gets a list of all users (Admin only).
     * GET /api/users/
     */
    getUsers: () => apiFetch('/users/'),

    /**
     * Gets a specific user by ID (Admin or self).
     * GET /api/users/{user_id}
     */
    getUserById: (userId) => apiFetch(`/users/${userId}`),

    /**
     * Updates the current user's profile.
     * PUT /api/users/me
     */
    updateCurrentUser: (userData) => apiFetch('/users/me', {
        method: 'PUT',
        body: userData, // { email, first_name, ... }
    }),
    

    // === Projects ===

    /**
     * Gets a list of all projects.
     * GET /api/projects
     */
    getProjects: () => apiFetch('/projects/'),

    /**
     * Creates a new project.
     * POST /api/projects
     */
    createProject: (projectData) => apiFetch('/projects/', {
        method: 'POST',
        body: projectData, // { project_key, project_name, ... }
    }),

    /**
     * Gets a single project by its ID.
     * GET /api/projects/{project_id}
     */
    getProjectById: (projectId) => apiFetch(`/projects/${projectId}`),

    /**
     * Updates an existing project.
     * PUT /api/projects/{project_id}
     */
    updateProject: (projectId, projectData) => apiFetch(`/projects/${projectId}`, {
        method: 'PUT',
        body: projectData,
    }),

    /**
     * Deletes a project.
     * DELETE /api/projects/{project_id}
     */
    deleteProject: (projectId) => apiFetch(`/projects/${projectId}`, {
        method: 'DELETE',
    }),


    // === Sprints ===

    /**
     * Gets all sprints for a specific project.
     * GET /api/projects/{project_id}/sprints
     */
    getSprintsForProject: (projectId) => apiFetch(`/projects/${projectId}/sprints`),

    /**
     * Creates a new sprint.
     * POST /api/sprints
     */
    createSprint: (sprintData) => apiFetch('/sprints/', {
        method: 'POST',
        body: sprintData, // { project_id, sprint_name, ... }
    }),

    /**
     * Gets a single sprint by its ID.
     * GET /api/sprints/{sprint_id}
     */
    getSprintById: (sprintId) => apiFetch(`/sprints/${sprintId}`),

    /**
     * Updates an existing sprint.
     * PUT /api/sprints/{sprint_id}
     */
    updateSprint: (sprintId, sprintData) => apiFetch(`/sprints/${sprintId}`, {
        method: 'PUT',
        body: sprintData,
    }),

    /**
     * Deletes a sprint.
     * DELETE /api/sprints/{sprint_id}
     */
    deleteSprint: (sprintId) => apiFetch(`/sprints/${sprintId}`, {
        method: 'DELETE',
    }),

    
    // === Issues ===

    /**
     * Gets all issues for a specific project.
     * GET /api/issues?project_id=...
     */
    getIssuesForProject: (projectId) => apiFetch(`/issues/?project_id=${projectId}`),

    /**
     * Gets all issues for a specific sprint.
     * GET /api/issues?sprint_id=...
     */
    getIssuesForSprint: (sprintId) => apiFetch(`/issues/?sprint_id=${sprintId}`),

    /**
     * Creates a new issue.
     * POST /api/issues
     */
    createIssue: (issueData) => apiFetch('/issues/', {
        method: 'POST',
        body: issueData,
    }),

    /**
     * Gets the detailed view for a single issue.
     * GET /api/issues/{issue_id}
     */
    getIssueDetails: (issueId) => apiFetch(`/issues/${issueId}`),

    /**
     * Updates an issue's general details.
     * PUT /api/issues/{issue_id}
     */
    updateIssue: (issueId, issueData) => apiFetch(`/issues/${issueId}`, {
        method: 'PUT',
        body: issueData,
    }),

    /**
     * Updates just the status of an issue.
     * PATCH /api/issues/{issue_id}/status
     */
    updateIssueStatus: (issueId, newStatus) => apiFetch(`/issues/${issueId}/status`, {
        method: 'PATCH',
        body: { status: newStatus },
    }),

    /**
     * Assigns an issue to a user.
     * PATCH /api/issues/{issue_id}/assign-user
     */
    assignIssueToUser: (issueId, userId) => apiFetch(`/issues/${issueId}/assign-user`, {
        method: 'PATCH',
        body: { assignee_id: userId }, // Pass null to unassign
    }),

    /**
     * Assigns an issue to a sprint.
     * PATCH /api/issues/{issue_id}/assign-sprint
     */
    assignIssueToSprint: (issueId, sprintId) => apiFetch(`/issues/${issueId}/assign-sprint`, {
        method: 'PATCH',
        body: { sprint_id: sprintId }, // Pass null to unassign
    }),

    /**
     * Deletes an issue.
     * DELETE /api/issues/{issue_id}
     */
    deleteIssue: (issueId) => apiFetch(`/issues/${issueId}`, {
        method: 'DELETE',
    }),


    // === Comments ===

    /**
     * Gets all comments for a specific issue.
     * GET /api/comments/by-issue/{issue_id}
     */
    getCommentsForIssue: (issueId) => apiFetch(`/comments/by-issue/${issueId}`),
    
    /**
     * Creates a new comment.
     * POST /api/comments
     */
    createComment: (issueId, commentText) => apiFetch('/comments/', {
        method: 'POST',
        body: { issue_id: issueId, comment_text: commentText },
    }),

    /**
     * Updates an existing comment.
     * PUT /api/comments/{comment_id}
     */
    updateComment: (commentId, commentText) => apiFetch(`/comments/${commentId}`, {
        method: 'PUT',
        body: { comment_text: commentText },
    }),

    /**
     * Deletes a comment.
     * DELETE /api/comments/{comment_id}
     */
    deleteComment: (commentId) => apiFetch(`/comments/${commentId}`, {
        method: 'DELETE',
    }),


    // === Worklogs ===

    /**
     * Gets all worklogs for a specific issue.
     * GET /api/worklogs/by-issue/{issue_id}
     */
    getWorklogsForIssue: (issueId) => apiFetch(`/worklogs/by-issue/${issueId}`),

    /**
     * Creates a new worklog.
     * POST /api/worklogs
     */
    createWorklog: (worklogData) => apiFetch('/worklogs/', {
        method: 'POST',
        body: worklogData, // { issue_id, hours_logged, work_date, ... }
    }),

    /**
     * Updates an existing worklog.
     * PUT /api/worklogs/{worklog_id}
     */
    updateWorklog: (worklogId, worklogData) => apiFetch(`/worklogs/${worklogId}`, {
        method: 'PUT',
        body: worklogData,
    }),

    /**
     * Deletes a worklog.
     * DELETE /api/worklogs/{worklog_id}
     */
    deleteWorklog: (worklogId) => apiFetch(`/worklogs/${worklogId}`, {
        method: 'DELETE',
    }),

    /**
     * Gets total hours logged for an issue.
     * GET /api/worklogs/by-issue/{issue_id}/total-hours
     */
    getTotalHoursForIssue: (issueId) => apiFetch(`/worklogs/by-issue/${issueId}/total-hours`),

    /**
     * Gets total hours logged for a project.
     * GET /api/worklogs/by-project/{project_id}/total-hours
     */
    getTotalHoursForProject: (projectId) => apiFetch(`/worklogs/by-project/${projectId}/total-hours`),

    /**
     * Gets hours logged per user for a project.
     * GET /api/worklogs/by-project/{project_id}/hours-by-user
     */
    getProjectHoursByUser: (projectId) => apiFetch(`/worklogs/by-project/${projectId}/hours-by-user`),


    // === Attachments ===

    /**
     * Gets all attachment metadata for an issue.
     * GET /api/attachments/by-issue/{issue_id}
     */
    getAttachmentsForIssue: (issueId) => apiFetch(`/attachments/by-issue/${issueId}`),

    /**
     * Uploads a new attachment for an issue.
     * POST /api/attachments/by-issue/{issue_id}
     */
    uploadAttachment: (issueId, file) => apiFetchFile(`/attachments/by-issue/${issueId}`, file),
    
    /**
     * Fetches a protected file and triggers a browser download.
     * Your backend's download endpoint is protected, so a simple <a href>
     * link will fail. We must use JavaScript to fetch the file with
     * the Authorization header and then build a temporary link to
     * trigger the download.
     */
    async downloadProtectedAttachment(attachmentId, filename) {
        const token = getToken();
        try {
            const response = await fetch(`${API_BASE_URL}/attachments/${attachmentId}/download`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                const errData = await response.json(); // Try to get error detail
                throw new Error(errData.detail || `HTTP Error: ${response.status}`);
            }

            // Get the file data as a "blob"
            const blob = await response.blob();
            
            // Create a temporary URL for the blob
            const url = window.URL.createObjectURL(blob);
            
            // Create a temporary link element
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename; // The filename to save as
            
            // Add the link to the page, click it, and remove it
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (err) {
            console.error('Download Error:', err);
            // We can show this error to the user
            alert(`Failed to download file: ${err.message}`);
        }
    },

    /**
     * Deletes an attachment.
     * DELETE /api/attachments/{attachment_id}
     */
    deleteAttachment: (attachmentId) => apiFetch(`/attachments/${attachmentId}`, {
        method: 'DELETE',
    }),

};