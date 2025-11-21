# Project Management System

A full-stack project management application built with FastAPI (Python) backend and vanilla JavaScript frontend using Pico CSS. This system provides comprehensive project tracking, issue management, sprint planning, and work logging capabilities.

## Features

### Core Functionality
- **User Authentication & Authorization**: JWT-based authentication with role-based access control (Admin/User)
- **Project Management**: Create, update, and manage projects with detailed metadata
- **Issue Tracking**: Full issue lifecycle management with custom types, priorities, and statuses
- **Sprint Planning**: Agile sprint management with timeline tracking
- **Work Logging**: Time tracking and work log entries per issue
- **File Attachments**: Upload and manage files associated with issues
- **Comments**: Collaborative commenting system on issues
- **Reports**: Work hour analytics per user and project

### Key Features
- RESTful API with comprehensive endpoint coverage
- Role-based access control (Admin/User roles)
- Database-backed storage with MySQL
- Responsive UI using Pico CSS framework
- Real-time error handling and validation
- Secure file upload/download functionality

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: MySQL
- **Authentication**: JWT (JSON Web Tokens)
- **Security**: bcrypt password hashing
- **API Documentation**: Auto-generated with Swagger/OpenAPI

### Frontend
- **Framework**: Vanilla JavaScript with Alpine.js patterns
- **CSS**: Pico CSS (classless CSS framework)
- **Architecture**: SPA-style with dynamic page loading
- **API Client**: Fetch API with centralized error handling

## Project Structure

```
.
├── frontend/                 # Frontend application
│   ├── css/
│   │   └── style.css        # Custom styles extending Pico CSS
│   ├── js/
│   │   ├── api.js           # Centralized API client
│   │   ├── auth.js          # Authentication utilities
│   │   └── utils.js         # Helper functions
│   ├── *.html               # Application pages
│   └── run.sh               # Frontend server script
│
├── server/                   # Backend application
│   ├── core/
│   │   └── security.py      # Security utilities
│   ├── crud/                # Database operations
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── issue.py
│   │   ├── sprint.py
│   │   ├── comment.py
│   │   ├── worklog.py
│   │   └── attachment.py
│   ├── database/
│   │   ├── db_utils.py      # Database connection utilities
│   │   └── init_schema.sql  # Database schema
│   ├── models/              # Pydantic models
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── issue.py
│   │   ├── sprint.py
│   │   ├── comment.py
│   │   ├── worklog.py
│   │   └── attachment.py
│   ├── routers/             # API endpoints
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   ├── issues.py
│   │   ├── sprints.py
│   │   ├── comments.py
│   │   ├── worklogs.py
│   │   └── attachments.py
│   ├── config.py            # Configuration management
│   ├── dependencies.py      # Shared dependencies
│   ├── main.py             # Application entry point
│   ├── requirements.txt    # Python dependencies
│   └── run.sh              # Backend server script
│
├── docker-compose.yml       # Docker orchestration
└── .gitignore
```

## Setup & Installation

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- Node.js (for serving frontend)

### Backend Setup

1. **Install Python dependencies**:
```bash
cd server
pip install -r requirements.txt
```

2. **Configure database**:
   - Create a MySQL database
   - Update `server/config.py` with your database credentials
   - Run the schema: `mysql -u your_user -p your_database < database/init_schema.sql`

3. **Run the backend**:
```bash
python main.py
# or
./run.sh
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend**:
```bash
cd frontend
```

2. **Serve the frontend** (using Python's built-in server):
```bash
python -m http.server 3000
# or
./run.sh
```

The frontend will be available at `http://localhost:3000`

### Docker Setup (Alternative)

```bash
docker-compose up
```

This will start both the backend and database services.

## API Documentation

Once the backend is running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Database Schema

The application uses a MySQL database with the following main entities:
- **User**: User accounts with authentication
- **Project**: Project containers with owner relationship
- **Sprint**: Time-boxed iteration periods
- **Issue**: Work items with type, priority, status
- **Comment**: Discussion threads on issues
- **Worklog**: Time tracking entries
- **Attachment**: File storage metadata

Key relationships:
- Projects have many Sprints and Issues
- Issues can have parent-child relationships
- Issues can be assigned to Users and Sprints
- Issues can have multiple Comments, Worklogs, and Attachments

## Usage

### Default Users
After running the schema initialization, an admin user is created:
- **Username**: `admin`
- **Password**: `admin123`

### Basic Workflow
1. **Login** with credentials
2. **Create a project** from the dashboard
3. **Add sprints** to organize work into iterations
4. **Create issues** to track work items
5. **Assign issues** to users and sprints
6. **Log work** to track time spent
7. **Add comments** for collaboration
8. **Attach files** for documentation

## Security Features

- Password hashing with bcrypt
- JWT token-based authentication
- Role-based authorization (Admin/User)
- CORS configuration for cross-origin requests
- SQL injection prevention via parameterized queries
- Secure file upload with validation

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token

### Users
- `GET /api/users/me` - Get current user
- `GET /api/users/{user_id}` - Get user by ID
- `PUT /api/users/{user_id}` - Update user
- `DELETE /api/users/{user_id}` - Delete user (Admin only)

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create project
- `GET /api/projects/{project_id}` - Get project details
- `PUT /api/projects/{project_id}` - Update project
- `DELETE /api/projects/{project_id}` - Delete project

### Issues
- `GET /api/projects/{project_id}/issues` - List project issues
- `POST /api/issues` - Create issue
- `GET /api/issues/{issue_id}` - Get issue details
- `PUT /api/issues/{issue_id}` - Update issue
- `DELETE /api/issues/{issue_id}` - Delete issue

### Sprints, Comments, Worklogs, Attachments
Similar CRUD operations available for all entities.

## Development

### Code Structure
- **Separation of Concerns**: Clear separation between routing, business logic, and data access
- **Pydantic Models**: Type-safe data validation
- **Dependency Injection**: FastAPI's dependency system for auth and database connections
- **Error Handling**: Comprehensive HTTP exception handling
- **Logging**: Structured logging throughout the application

### Adding New Features
1. Define Pydantic models in `server/models/`
2. Create CRUD operations in `server/crud/`
3. Add API routes in `server/routers/`
4. Update frontend API client in `frontend/js/api.js`
5. Create/update UI pages in `frontend/`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create a Pull Request

## License

This project is available for educational and commercial use.

## Support

For issues, questions, or contributions, please open an issue on the project repository.

---

**Built using FastAPI and modern web technologies**
