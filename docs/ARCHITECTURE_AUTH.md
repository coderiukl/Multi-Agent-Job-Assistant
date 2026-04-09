# 🔐 Luồng xác thực (Authentication Flow)

## Tổng quan

Module auth quản lý:
- 📝 **Đăng ký** tài khoản mới
- 🔑 **Đăng nhập** với email/password
- 🔄 **Refresh token** để giữ session
- 🚪 **Đăng xuất** từ hệ thống

---

## 1️⃣ Đăng ký (Register)

### Endpoint
```
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepass123",
  "full_name": "Nguyễn Văn A"
}
```

### Response (201 Created)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Nguyễn Văn A",
  "is_active": true,
  "created_at": "2026-04-10T10:00:00Z"
}
```

### Luồng xử lý
```
1. Nhận RegisterRequest từ client
   ↓
2. Kiểm tra email đã tồn tại?
   ├─ Có → Trả về 400: "Email đã được đăng ký"
   └─ Không → Tiếp tục
   ↓
3. Hash password: password → hash_password()
   ↓
4. Tạo User object:
   - email
   - full_name  
   - password_hash (không lưu plain text)
   - is_active = True
   ↓
5. Lưu vào PostgreSQL
   ↓
6. Trả về UserResponse (db.flush() để lấy id)
```

### Security
- ✅ Password được hash với `hash_password()` (dùng bcrypt)
- ✅ Không lưu password plain text
- ✅ Kiểm tra email trùng lặp

---

## 2️⃣ Đăng nhập (Login)

### Endpoint
```
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepass123"
}
```

### Response (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Luồng xử lý

```
1. Nhận LoginRequest (email + password)
   ↓
2. Tìm User trong DB:
   SELECT * FROM users WHERE email = ?
   ├─ User không tồn tại → Trả về 401: "Email hoặc mật khẩu không đúng"
   └─ User tồn tại → Tiếp tục
   ↓
3. Verify password:
   verify_password(input_password, user.password_hash)
   ├─ Sai → Trả về 401: "Email hoặc mật khẩu không đúng"
   └─ Đúng → Tiếp tục
   ↓
4. Kiểm tra tài khoản có active?
   ├─ is_active = False → Trả về 403: "Tài khoản đã bị khóa"
   └─ is_active = True → Tiếp tục
   ↓
5. Tạo tokens:
   - access_token: JWT ngắn hạn (30 phút, settings.ACCESS_TOKEN_EXPIRE_MINUTES)
   - refresh_token: ngẫu nhiên dài hạn (7 ngày, settings.REFRESH_TOKEN_EXPIRE_DAYS)
   ↓
6. Lưu refresh_token vào DB:
   INSERT INTO refresh_tokens {
     user_id: user.id,
     token_hash: hash(refresh_token),  // hash refresh_token trước khi lưu
     expires_at: now + 7 days,
     user_agent: request.headers["user-agent"],
     ip_address: request.client.host
   }
   ↓
7. Trả về TokenResponse (access_token + refresh_token + type)
```

### Security Details

**Access Token (JWT)**
- Format: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...`
- Payload:
  ```json
  {
    "sub": "user-uuid",
    "exp": 1234567890,
    "iat": 1234567800
  }
  ```
- Dùng để gọi API (gửi header `Authorization: Bearer <access_token>`)
- **Hết hạn sau 30 phút**

**Refresh Token**
- Chuỗi bí mật dài ngẫu nhiên
- Hash được lưu trong DB (không lưu plain text)
- Dùng để lấy access_token mới mà không cần nhập lại password
- **Hết hạn sau 7 ngày**

**User Agent & IP Tracking**
- Lưu `user-agent` (browser info) và `ip_address` để detect login từ thiết bị lạ
- Có thể dùng cho multi-device logout hoặc security alerts

---

## 3️⃣ Refresh Token (Làm mới token)

### Endpoint
```
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Response (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Luồng xử lý

```
1. Nhận refresh_token từ client
   ↓
2. Hash token: hash_refresh_token(refresh_token)
   ↓
3. Tìm token record trong DB:
   SELECT * FROM refresh_tokens WHERE token_hash = ?
   ├─ Không tìm thấy → Trả về 401: "Refresh token không hợp lệ"
   └─ Tìm thấy → Tiếp tục
   ↓
4. Kiểm tra token có bị revoke không:
   if token_record.revoked_at IS NOT NULL:
     ├─ Đã revoke → Có thể là replay attack, logout tất cả sessions
     └─ Chưa revoke → Tiếp tục
   ↓
5. Kiểm tra token còn hết hạn?
   if token_record.expires_at < now:
     ├─ Hết hạn → Trả về 401: "Refresh token đã hết hạn"
     └─ Còn hạn → Tiếp tục
   ↓
6. Revoke token cũ:
   UPDATE refresh_tokens 
   SET revoked_at = NOW() 
   WHERE id = ?
   
   (Tránh tái sử dụng token cũ)
   ↓
7. Tạo token pair mới:
   - access_token mới (JWT 30 phút)
   - refresh_token mới
   ↓
8. Lưu refresh_token mới vào DB:
   INSERT INTO refresh_tokens {
     user_id: token_record.user_id,
     token_hash: hash(new_refresh_token),
     expires_at: now + 7 days,
     user_agent: token_record.user_agent,
     ip_address: token_record.ip_address
   }
   ↓
9. Trả về TokenResponse mới
```

### Mục đích
- Access token hết hạn → gọi refresh để lấy cái mới
- Không cần nhập lại password
- Kéo dài session mà vẫn giữ security (token ngắn hạn)

---

## 4️⃣ Đăng xuất (Logout)

### Endpoint
```
POST /api/auth/logout
Header: Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Response (204 No Content)
- Không trả về body

### Luồng xử lý

```
1. Verify current_user (từ access_token)
   GET /me + Authorization header
   ├─ Invalid token → 401
   └─ Valid token → Lấy user info, tiếp tục
   ↓
2. Nhận refresh_token từ request body
   ↓
3. Hash refresh_token
   ↓
4. Tìm token record:
   SELECT * FROM refresh_tokens 
   WHERE token_hash = ? AND user_id = ?
   ├─ Không tìm → Skip (có thể token đã được revoke)
   └─ Tìm thấy → Tiếp tục
   ↓
5. Kiểm tra token chưa revoke:
   if token_record.revoked_at IS NULL:
     ├─ Chưa revoke → Tiếp tục
     └─ Đã revoke → Skip
   ↓
6. Revoke token:
   UPDATE refresh_tokens 
   SET revoked_at = NOW() 
   WHERE id = ?
   ↓
7. Trả về 204 No Content
```

### Kết quả
- Refresh token không còn sử dụng được
- Access token vẫn valid cho đến khi hết hạn (nhưng không thể refresh)
- User phải login lại để gọi API protected

---

## 5️⃣ Lấy thông tin user (Get Me)

### Endpoint
```
GET /api/auth/me
Header: Authorization: Bearer <access_token>
```

### Response (200 OK)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Nguyễn Văn A",
  "is_active": true,
  "created_at": "2026-04-10T10:00:00Z"
}
```

### Luồng xử lý
```
1. Verify access_token từ header Authorization
   ├─ Missing hoặc invalid → 401 Unauthorized
   └─ Valid → Tiếp tục
   ↓
2. Lấy user_id từ JWT payload (sub claim)
   ↓
3. SELECT * FROM users WHERE id = user_id
   ├─ Không tìm → 404 Not Found
   └─ Tìm thấy → Tiếp tục
   ↓
4. Trả về UserResponse
```

---

## 📊 Database Schema

### users table
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  full_name VARCHAR NOT NULL,
  password_hash VARCHAR NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);
```

### refresh_tokens table
```sql
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  token_hash VARCHAR NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP,
  user_agent VARCHAR,
  ip_address VARCHAR,
  created_at TIMESTAMP DEFAULT now()
);

-- Indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

---

## 🔒 Security Best Practices

### 1. Password Storage
- ✅ Hash với bcrypt (passlib library)
- ❌ Không lưu plain text password

### 2. Token Management
- ✅ Access token ngắn hạn (30 phút)
- ✅ Refresh token dài hạn (7 ngày)
- ✅ Refresh token được hash trước lưu DB
- ✅ Revoke token khi logout
- ✅ Revoke refresh token cũ khi refresh

### 3. Session Tracking
- ✅ Lưu user_agent (browser info)
- ✅ Lưu IP address
- ✅ Có thể detect suspicious login attempts

### 4. Error Messages
- ✅ Generic error: "Email hoặc mật khẩu không đúng"
- ✅ Không reveal nếu email tồn tại hay không (prevent user enumeration)

---

## 📝 Implementation Files

- **Router**: [app/routers/auth.py](../backend/app/routers/auth.py)
- **Security utilities**: [app/core/security.py](../backend/app/core/security.py)
- **Database models**: [app/db/models.py](../backend/app/db/models.py)
- **Schemas**: [app/schemas/auth.py](../backend/app/schemas/auth.py)
- **Dependencies**: [app/core/dependencies.py](../backend/app/core/dependencies.py)

---

## 🧪 Example cURL Commands

### Register
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "full_name": "Nguyễn Văn A"
  }'
```

### Login
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123"
  }'

# Response: {access_token, refresh_token}
# Save tokens!
```

### Get Me
```bash
export TOKEN="<access_token_from_login>"
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

### Refresh Token
```bash
export REFRESH_TOKEN="<refresh_token_from_login>"
curl -X POST "http://localhost:8000/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# Trả về access_token + refresh_token mới
```

### Logout
```bash
export TOKEN="<access_token>"
export REFRESH_TOKEN="<refresh_token>"

curl -X POST "http://localhost:8000/api/auth/logout" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# Response: 204 No Content
```
