# Creatio Marketplace - Backend README

## Overview

Creatio is a premium marketplace for the creator economy, connecting creators to businesses. This backend provides a comprehensive API for:

- **User Authentication & Authorization** (JWT-based)
- **Gig Lifecycle Management** (State Machine: OPEN → FUNDED → IN_PROGRESS → SUBMITTED → APPROVED/DISPUTED)
- **Wallet System** with Paystack integration (Deposits, Withdrawals, Escrow)
- **Messaging Platform** for business-creator communication
- **Dispute Resolution System** with admin mediation
- **Proof of Work (PoW)** module with S3 storage and auto-release
- **Analytics Dashboard** and Leaderboard
- **Notification System**

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy 2.0
- **Authentication**: JWT (python-jose)
- **Payments**: Paystack API (15% Platform / 85% Creator split)
- **Storage**: S3-Compatible (for PoW files)
- **Task Queue**: Redis (for background jobs)

## Project Structure

```
backend/
├── app/
│   ├── core/           # Config, Database, Security
│   ├── models/         # SQLAlchemy ORM Models
│   ├── schemas/        # Pydantic Schemas
│   ├── services/       # Business Logic Services
│   ├── routes/         # API Endpoints
│   ├── utils/          # Helper utilities
│   └── main.py         # FastAPI Application
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Paystack Account (for payments)

### Setup Steps

1. **Clone the repository**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Set up PostgreSQL database**
   ```sql
   CREATE DATABASE creatio_db;
   ```

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication (`/api/v1/auth`)
- `POST /register` - Register new user
- `POST /login` - Login and get tokens
- `GET /me` - Get current user info
- `PUT /profile` - Update profile
- `POST /verification/request` - Request verification
- `POST /verification/complete` - Complete verification

### Gigs (`/api/v1/gigs`)
- `POST /` - Create gig (Business only)
- `GET /` - List gigs
- `GET /marketplace` - Browse marketplace
- `GET /{gig_id}` - Get gig details
- `POST /{gig_id}/fund` - Fund gig (lock escrow)
- `POST /{gig_id}/accept` - Accept gig (Creator)
- `POST /{gig_id}/submit-pow` - Submit Proof of Work
- `POST /{gig_id}/approve` - Approve and release funds

### Wallet (`/api/v1/wallet`)
- `GET /balance` - Get wallet balance
- `POST /deposit/initialize` - Initialize Paystack deposit
- `POST /deposit/verify/{reference}` - Verify deposit
- `POST /withdraw` - Request withdrawal
- `GET /deposits` - Deposit history
- `GET /withdrawals` - Withdrawal history

### Messages (`/api/v1/messages`)
- `POST /` - Send message
- `GET /gig/{gig_id}` - Get chat history
- `GET /inbox` - Get inbox
- `POST /pitch/{gig_id}` - Submit pitch

### Disputes (`/api/v1/disputes`)
- `POST /` - Create dispute
- `GET /` - List disputes
- `GET /{dispute_id}` - Get dispute details
- `POST /{dispute_id}/resolve` - Resolve dispute (Admin)

### Notifications (`/api/v1/notifications`)
- `GET /` - Get notifications
- `GET /unread-count` - Get unread count
- `POST /{id}/read` - Mark as read
- `POST /read-all` - Mark all as read

### Analytics (`/api/v1/analytics`)
- `GET /my-analytics` - User analytics
- `GET /leaderboard` - Top earners leaderboard
- `GET /creators` - Verified creators
- `GET /marketplace-stats` - Marketplace statistics

## Gig Lifecycle State Machine

```
OPEN → FUNDED → IN_PROGRESS → SUBMITTED → APPROVED
                              ↓
                          DISPUTED → RESOLVED
```

### Status Descriptions

| Status | Description |
|--------|-------------|
| OPEN | Gig created, waiting for funding |
| FUNDED | Escrow locked, ready for work |
| IN_PROGRESS | Creator working on gig |
| SUBMITTED | PoW uploaded, awaiting approval |
| APPROVED | Funds released to creator |
| DISPUTED | Dispute raised, escrow frozen |
| RESOLVED | Admin resolved dispute |

## Payment Flow

1. **Business deposits funds** via Paystack → Wallet (Available Balance)
2. **Business funds gig** → Wallet (Locked Balance / Escrow)
3. **Creator completes work** → Submits PoW
4. **Business approves** → 85% to Creator, 15% to Platform
5. **Creator withdraws** → Bank account via Paystack Transfer

## Dispute Resolution

Either party can raise a dispute when gig status is `SUBMITTED` or `IN_PROGRESS`:

1. **Dispute Created** → Escrow frozen
2. **Admin notified** → Reviews chat history + PoW
3. **Admin resolves** with one of:
   - **Force Release**: Full amount to creator
   - **Full Refund**: Full amount back to business
   - **Partial Split**: Custom split defined by admin

## Auto-Release Feature

If a business doesn't approve or dispute within `POW_AUTO_RELEASE_DAYS` (default: 7 days) after PoW submission, funds are automatically released to the creator.

## Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control (Creator, Business, Admin)
- CORS configuration
- Input validation with Pydantic

## License

MIT License
