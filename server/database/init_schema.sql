-- Drop tables in reverse order of dependency if they exist (for easy reset)
DROP TABLE IF EXISTS Worklog;
DROP TABLE IF EXISTS Attachment;
DROP TABLE IF EXISTS Comment;
DROP TABLE IF EXISTS Issue;
DROP TABLE IF EXISTS Sprint;
DROP TABLE IF EXISTS Project;
DROP TABLE IF EXISTS User;

-- Drop procedures and functions if they exist
DROP PROCEDURE IF EXISTS CreateProject;
DROP PROCEDURE IF EXISTS CreateIssue;
DROP PROCEDURE IF EXISTS AddComment;
DROP PROCEDURE IF EXISTS LogWork;
DROP PROCEDURE IF EXISTS AssignIssueToSprint;
DROP PROCEDURE IF EXISTS UpdateIssueStatus;
DROP FUNCTION IF EXISTS CalculateTotalIssueHours;
DROP FUNCTION IF EXISTS GetUserIssueCount;
DROP FUNCTION IF EXISTS GetProjectIssueCount;

-- --- TABLE DEFINITIONS ---

-- User Table
CREATE TABLE User (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL COMMENT 'Store hashed passwords only',
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    role VARCHAR(50) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin', 'project_manager')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT 'Stores user information and credentials';

-- Project Table
CREATE TABLE Project (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    project_key VARCHAR(10) UNIQUE NOT NULL COMMENT 'Short identifier for the project (e.g., DEMO)',
    project_name VARCHAR(255) NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'planning' CHECK (status IN ('planning', 'active', 'completed', 'archived')),
    owner_id INT COMMENT 'User who owns/created the project',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES User(user_id) ON DELETE SET NULL
) COMMENT 'Stores project details';

-- Sprint Table
CREATE TABLE Sprint (
    sprint_id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    sprint_name VARCHAR(255) NOT NULL,
    goal TEXT,
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'future' CHECK (status IN ('future', 'active', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES Project(project_id) ON DELETE CASCADE
) COMMENT 'Stores sprint information within a project';

-- Issue Table
CREATE TABLE Issue (
    issue_id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    sprint_id INT NULL COMMENT 'Which sprint the issue belongs to (can be null)',
    description TEXT NOT NULL,
    issue_type VARCHAR(50) NOT NULL DEFAULT 'Task' CHECK (issue_type IN ('Task', 'Bug', 'Story', 'Epic')),
    priority VARCHAR(50) NOT NULL DEFAULT 'Medium' CHECK (priority IN ('Highest', 'High', 'Medium', 'Low', 'Lowest')),
    status VARCHAR(50) NOT NULL DEFAULT 'To Do' CHECK (status IN ('To Do', 'In Progress', 'In Review', 'Done', 'Blocked')),
    reporter_id INT COMMENT 'User who reported the issue',
    assignee_id INT NULL COMMENT 'User assigned to the issue (can be null)',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date DATE NULL,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    story_points INT NULL COMMENT 'Estimation points (optional)',
    parent_issue_id INT NULL COMMENT 'For sub-tasks linking to a parent issue',
    FOREIGN KEY (project_id) REFERENCES Project(project_id) ON DELETE CASCADE,
    FOREIGN KEY (sprint_id) REFERENCES Sprint(sprint_id) ON DELETE SET NULL,
    FOREIGN KEY (reporter_id) REFERENCES User(user_id) ON DELETE SET NULL,
    FOREIGN KEY (assignee_id) REFERENCES User(user_id) ON DELETE SET NULL,
    FOREIGN KEY (parent_issue_id) REFERENCES Issue(issue_id) ON DELETE SET NULL -- Self-referencing FK
) COMMENT 'Stores details about tasks, bugs, stories, etc.';

-- Comment Table
CREATE TABLE Comment (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    issue_id INT NOT NULL,
    user_id INT COMMENT 'User who wrote the comment',
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Allow tracking comment edits',
    FOREIGN KEY (issue_id) REFERENCES Issue(issue_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE SET NULL
) COMMENT 'Stores comments related to issues';

-- Attachment Table
CREATE TABLE Attachment (
    attachment_id INT AUTO_INCREMENT PRIMARY KEY,
    issue_id INT NOT NULL,
    user_id INT COMMENT 'User who uploaded the attachment',
    file_name VARCHAR(255) NOT NULL COMMENT 'Original file name',
    file_path VARCHAR(512) NOT NULL UNIQUE COMMENT 'Server path where file is stored',
    file_type VARCHAR(100) COMMENT 'MIME type of the file',
    file_size_bytes BIGINT COMMENT 'Size of the file in bytes',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES Issue(issue_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE SET NULL
) COMMENT 'Stores metadata about files attached to issues';

-- Worklog Table
CREATE TABLE Worklog (
    worklog_id INT AUTO_INCREMENT PRIMARY KEY,
    issue_id INT NOT NULL,
    user_id INT COMMENT 'User who logged the work',
    hours_logged DECIMAL(5, 2) NOT NULL CHECK (hours_logged > 0),
    work_date DATE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES Issue(issue_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE SET NULL
) COMMENT 'Stores time tracking entries for issues';

-- --- INDEXES ---
-- Create indexes for commonly queried columns to improve performance
CREATE INDEX idx_issue_project ON Issue (project_id);
CREATE INDEX idx_issue_sprint ON Issue (sprint_id);
CREATE INDEX idx_issue_assignee ON Issue (assignee_id);
CREATE INDEX idx_issue_reporter ON Issue (reporter_id);
CREATE INDEX idx_issue_parent ON Issue (parent_issue_id);
CREATE INDEX idx_comment_issue ON Comment (issue_id);
CREATE INDEX idx_comment_user ON Comment (user_id);
CREATE INDEX idx_attachment_issue ON Attachment (issue_id);
CREATE INDEX idx_attachment_user ON Attachment (user_id);
CREATE INDEX idx_worklog_issue ON Worklog (issue_id);
CREATE INDEX idx_worklog_user ON Worklog (user_id);
CREATE INDEX idx_sprint_project ON Sprint (project_id);


-- --- TRIGGERS ---

-- Trigger: Update Issue's updated_date when a comment is added
DELIMITER $$
CREATE TRIGGER after_comment_insert
AFTER INSERT ON Comment
FOR EACH ROW
BEGIN
    UPDATE Issue SET updated_date = CURRENT_TIMESTAMP WHERE issue_id = NEW.issue_id;
END$$
DELIMITER ;

-- Trigger: Update Issue's updated_date when a comment is updated
DELIMITER $$
CREATE TRIGGER after_comment_update
AFTER UPDATE ON Comment
FOR EACH ROW
BEGIN
    -- Only update if the comment text actually changed
    IF OLD.comment_text <> NEW.comment_text THEN
        UPDATE Issue SET updated_date = CURRENT_TIMESTAMP WHERE issue_id = NEW.issue_id;
    END IF;
END$$
DELIMITER ;

-- Trigger: Update Issue's updated_date when a worklog is added
DELIMITER $$
CREATE TRIGGER after_worklog_insert
AFTER INSERT ON Worklog
FOR EACH ROW
BEGIN
    UPDATE Issue SET updated_date = CURRENT_TIMESTAMP WHERE issue_id = NEW.issue_id;
END$$
DELIMITER ;

-- Trigger: Update Issue's updated_date when an attachment is added
DELIMITER $$
CREATE TRIGGER after_attachment_insert
AFTER INSERT ON Attachment
FOR EACH ROW
BEGIN
    UPDATE Issue SET updated_date = CURRENT_TIMESTAMP WHERE issue_id = NEW.issue_id;
END$$
DELIMITER ;

-- Trigger: Prevent assigning an issue to a sprint of a different project (demonstrates complex check)
DELIMITER $$
CREATE TRIGGER before_issue_sprint_check
BEFORE UPDATE ON Issue
FOR EACH ROW
BEGIN
    DECLARE sprint_project_id INT;
    -- Check only if sprint_id is being changed to a non-null value
    IF NEW.sprint_id IS NOT NULL AND (OLD.sprint_id IS NULL OR OLD.sprint_id <> NEW.sprint_id) THEN
        SELECT project_id INTO sprint_project_id FROM Sprint WHERE sprint_id = NEW.sprint_id;
        IF sprint_project_id <> NEW.project_id THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot assign issue to a sprint belonging to a different project.';
        END IF;
    END IF;
END$$
DELIMITER ;


-- --- FUNCTIONS ---

-- Function: Calculate total hours logged for a specific issue (Demonstrates AGGREGATE)
DELIMITER $$
CREATE FUNCTION CalculateTotalIssueHours(p_issue_id INT)
RETURNS DECIMAL(10, 2)
DETERMINISTIC
READS SQL DATA -- Indicates the function reads data
BEGIN
    DECLARE total_hours DECIMAL(10, 2);
    SELECT SUM(hours_logged) INTO total_hours
    FROM Worklog
    WHERE issue_id = p_issue_id;
    RETURN IFNULL(total_hours, 0.00);
END$$
DELIMITER ;

-- Function: Get count of issues for a user (reporter or assignee)
DELIMITER $$
CREATE FUNCTION GetUserIssueCount(p_user_id INT, p_role VARCHAR(10)) -- p_role can be 'reporter' or 'assignee'
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE issue_count INT;
    IF p_role = 'reporter' THEN
        SELECT COUNT(*) INTO issue_count FROM Issue WHERE reporter_id = p_user_id;
    ELSEIF p_role = 'assignee' THEN
        SELECT COUNT(*) INTO issue_count FROM Issue WHERE assignee_id = p_user_id;
    ELSE
        SET issue_count = 0;
    END IF;
    RETURN IFNULL(issue_count, 0);
END$$
DELIMITER ;

-- Function: Get count of issues within a specific project
DELIMITER $$
CREATE FUNCTION GetProjectIssueCount(p_project_id INT)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE issue_count INT;
    SELECT COUNT(*) INTO issue_count FROM Issue WHERE project_id = p_project_id;
    RETURN IFNULL(issue_count, 0);
END$$
DELIMITER ;


-- --- STORED PROCEDURES ---

-- Procedure: Create a new project
DELIMITER $$
CREATE PROCEDURE CreateProject(
    IN p_project_key VARCHAR(10),
    IN p_project_name VARCHAR(255),
    IN p_description TEXT,
    IN p_owner_id INT,
    OUT p_project_id INT
)
BEGIN
    INSERT INTO Project (project_key, project_name, description, owner_id, status)
    VALUES (p_project_key, p_project_name, p_description, p_owner_id, 'planning');
    SET p_project_id = LAST_INSERT_ID();
END$$
DELIMITER ;

-- Procedure: Create a new issue (Demonstrates NESTED QUERY / SUBQUERY)
DELIMITER $$
CREATE PROCEDURE CreateIssue(
    IN p_project_id INT,
    IN p_description TEXT,
    IN p_issue_type VARCHAR(50),
    IN p_priority VARCHAR(50),
    IN p_reporter_id INT,
    IN p_assignee_id INT,
    IN p_sprint_id INT,
    IN p_due_date DATE,
    IN p_story_points INT,
    IN p_parent_issue_id INT,
    OUT p_issue_id INT
)
BEGIN
    -- Validation using nested EXISTS subqueries
    IF NOT EXISTS (SELECT 1 FROM Project WHERE project_id = p_project_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Project does not exist.';
    END IF;

    IF p_sprint_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM Sprint WHERE sprint_id = p_sprint_id AND project_id = p_project_id) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Sprint does not belong to the specified project.';
        END IF;
    END IF;

     IF p_parent_issue_id IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM Issue WHERE issue_id = p_parent_issue_id AND project_id = p_project_id) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Parent issue does not belong to the specified project.';
        END IF;
    END IF;


    INSERT INTO Issue (project_id, description, issue_type, priority, reporter_id, assignee_id, sprint_id, due_date, story_points, parent_issue_id, status)
    VALUES (p_project_id, p_description, p_issue_type, p_priority, p_reporter_id, p_assignee_id, p_sprint_id, p_due_date, p_story_points, p_parent_issue_id, 'To Do'); -- Default status
    
    SET p_issue_id = LAST_INSERT_ID();
END$$
DELIMITER ;

-- Procedure: Add a comment to an issue
DELIMITER $$
CREATE PROCEDURE AddComment(
    IN p_issue_id INT,
    IN p_user_id INT,
    IN p_comment_text TEXT,
    OUT p_comment_id INT
)
BEGIN
    INSERT INTO Comment (issue_id, user_id, comment_text)
    VALUES (p_issue_id, p_user_id, p_comment_text);
    SET p_comment_id = LAST_INSERT_ID();
    -- The after_comment_insert trigger handles updating Issue.updated_date
END$$
DELIMITER ;

-- Procedure: Log work on an issue
DELIMITER $$
CREATE PROCEDURE LogWork(
    IN p_issue_id INT,
    IN p_user_id INT,
    IN p_hours_logged DECIMAL(5, 2),
    IN p_work_date DATE,
    IN p_description TEXT,
    OUT p_worklog_id INT
)
BEGIN
    INSERT INTO Worklog (issue_id, user_id, hours_logged, work_date, description)
    VALUES (p_issue_id, p_user_id, p_hours_logged, p_work_date, p_description);
    SET p_worklog_id = LAST_INSERT_ID();
    -- The after_worklog_insert trigger handles updating Issue.updated_date
END$$
DELIMITER ;

-- Procedure: Assign an issue to a sprint (Demonstrates NESTED QUERY / SUBQUERY)
DELIMITER $$
CREATE PROCEDURE AssignIssueToSprint(
    IN p_issue_id INT,
    IN p_sprint_id INT
)
BEGIN
    DECLARE issue_project_id INT;

    -- Get the project ID of the issue
    SELECT project_id INTO issue_project_id FROM Issue WHERE issue_id = p_issue_id;

    -- Check if sprint exists and belongs to the same project (nested query)
    IF p_sprint_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM Sprint WHERE sprint_id = p_sprint_id AND project_id = issue_project_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Target sprint does not exist or belongs to a different project.';
    END IF;

    UPDATE Issue SET sprint_id = p_sprint_id, updated_date = CURRENT_TIMESTAMP WHERE issue_id = p_issue_id;
END$$
DELIMITER ;

-- Procedure: Update the status of an issue
DELIMITER $$
CREATE PROCEDURE UpdateIssueStatus(
    IN p_issue_id INT,
    IN p_new_status VARCHAR(50)
)
BEGIN
    -- You could add logic here to validate status transitions, e.g.,
    -- DECLARE current_status VARCHAR(50);
    -- SELECT status INTO current_status FROM Issue WHERE issue_id = p_issue_id;
    -- IF current_status = 'Done' AND p_new_status <> 'Done' THEN
    --    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cannot move issue out of Done status (example rule).';
    -- END IF;

    UPDATE Issue SET status = p_new_status, updated_date = CURRENT_TIMESTAMP WHERE issue_id = p_issue_id;
END$$
DELIMITER ;

-- --- END SQL FEATURES ---

SELECT 'Schema creation and feature setup complete.' AS Status;
