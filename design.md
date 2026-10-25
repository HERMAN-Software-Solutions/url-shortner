# Week 1 — URL Shortener with Analytics: Design Doc

**Intern:** Angella Tendo · **Mentor:** Jiang Salim ·


## 1. What the system does

The system allows users to turn long URLs into shorter links that are easier to share. When someone opens a short link, the system redirects them to the original webpage and records the visit. Users can view statistics to see how many times their links have been clicked.

## 2. API Surface

* `POST /auth/register` → Creates a user account and returns the user's details.
* `POST /auth/login` → Checks the user's credentials and returns a JWT access token.
* `POST /shorten` → Creates a short link and returns the short code and original URL. Requires authentication.
* `GET /{short_code}` → Redirects the user to the original URL and records the click.
* `GET /stats/{code}` → Returns click statistics for a link. Requires authentication.
* `DELETE /links/{code}` → Deletes a link. Requires authentication.

## 3. Database Schema

### 3.1 Users Table

Stores registered user accounts and login details.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary Key |
| `email` | VARCHAR(255) | Unique, Not Null |
| `password_hash` | VARCHAR(255) | Not Null |
| `created_at` | TIMESTAMPTZ | Not Null |

The `password_hash` stores a securely hashed password, never the plain password.

### 3.2 Links Table

Stores the original URLs, their short codes, and the users who created them.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary Key |
| `user_id` | UUID | Foreign Key → `users.id`, Not Null |
| `short_code` | VARCHAR(20) | Unique, Not Null |
| `original_url` | TEXT | Not Null |
| `created_at` | TIMESTAMPTZ | Not Null |
| `is_active` | BOOLEAN | Not Null, Default TRUE |

### 3.3 Click Events Table

Stores individual visits to shortened links for analytics.

| Column | Type | Constraints |
|---|---|---|
| `id` | BIGINT | Primary Key |
| `link_id` | UUID | Foreign Key → `links.id`, Not Null |
| `clicked_at` | TIMESTAMPTZ | Not Null |
| `referrer` | TEXT | Nullable |

### Indexes

- **`users(email)` — Unique index:** Speeds up login lookups and prevents duplicate accounts.
- **`links(short_code)` — Unique index:** Quickly finds the original URL during a redirect and prevents duplicate short codes.
- **`links(user_id)` — Index:** Speeds up queries for links belonging to a user.
- **`click_events(link_id, clicked_at)` — Index:** Speeds up click statistics for a link over a specific time period.

### Click Storage Decision

I will store each click as a separate row in the `click_events` table. This supports total clicks, clicks per day or hour, and comparisons between links. The trade-off is that the table will grow as traffic increases, requiring additional storage and potentially aggregation for faster analytics.

## 4. Tech Choices

- **Framework — FastAPI:** I will use FastAPI because I have already worked with it, and it provides request validation and tools for building APIs efficiently.
- **Database — PostgreSQL:** I will use PostgreSQL because it handles multiple users accessing and changing data more reliably than SQLite in a production application.
- **Cache — Redis:** I will use Redis to temporarily store frequently accessed short-code lookups in memory, reducing database queries and making redirects faster.
- **Authentication — JWT:** I will use JWTs because a signed token allows the application to verify a user's identity on protected requests without querying the database to validate the token each time.
- **Deployment — Docker:** I will use Docker to package the application and its dependencies into a container so it can run consistently across development and deployment environments.

## 5. Open Questions

1. **Link management:** Should users be able to view all their links and edit their original URLs?
2. **Analytics:** Should click statistics be grouped by day, hour, or both?
3. **Click recording:** Should click events be saved before or after redirecting to keep redirects fast?
4. **Caching:** How long should Redis keep a short-code lookup, and how should cached entries be removed when a link is deleted?
5. **Link deletion:** Should links be permanently deleted or marked inactive to preserve their click history? I am leaning towards marking them inactive.
6. **Short-code generation:** Should short codes use random characters or another method, and how should duplicate codes be handled? My initial assumption is to generate random codes and enforce uniqueness in the database.
7. **Redirect behavior:** Should the system use a 301 or 302 redirect? I am leaning towards 302 to reduce browser caching that could bypass the server and affect click counting.
8. **Authentication:** How long should JWT access tokens remain valid, and how should logout work?
9. **Click data and growth:** Should the system record additional details, such as user agents or country, considering privacy? How should click events be managed as the table grows?
10. **Input and usage limits:** Should the system validate submitted URLs and limit how many short links a user can create within a given time?

### Decision

Creating a short link through `POST /shorten` will require authentication so that every link has an identified owner.