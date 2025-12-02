# Frontend Authentication Implementation Guide
## VisionGuard AI - React/Next.js Frontend Integration

This guide provides a complete implementation roadmap for integrating authentication with the VisionGuard AI backend in your React or Next.js frontend application.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Environment Setup](#environment-setup)
4. [Authentication Context & State Management](#authentication-context--state-management)
5. [API Client Setup](#api-client-setup)
6. [Authentication Components](#authentication-components)
7. [Protected Routes](#protected-routes)
8. [Shop Management](#shop-management)
9. [WebRTC Integration with Auth](#webrtc-integration-with-auth)
10. [WebSocket Integration with Auth](#websocket-integration-with-auth)
11. [Complete Code Examples](#complete-code-examples)

---

## Overview

The VisionGuard AI backend now includes:
- **JWT-based authentication** (access & refresh tokens)
- **Role-based authorization** (OWNER and MANAGER roles)
- **Shop management** with manager assignments
- **Protected WebRTC** and WebSocket endpoints

Your frontend must:
- Handle user registration and login
- Store and manage JWT tokens securely
- Include tokens in API requests, WebRTC offers, and WebSocket connections
- Implement role-based UI rendering
- Manage shop-specific video streams

---

## Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                                                                  │
│  User Input (Email/Password)                                    │
│          ↓                                                       │
│  POST /auth/login or /auth/register-owner                       │
│          ↓                                                       │
│  Receive: { access_token, refresh_token, user: {...} }          │
│          ↓                                                       │
│  Store tokens in: localStorage/sessionStorage/memory            │
│          ↓                                                       │
│  Include in all requests: Authorization: Bearer <token>         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│                                                                  │
│  Verify JWT Token → Extract user info → Check permissions       │
│          ↓                                                       │
│  Allow/Deny request based on role and shop access               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Role-Based Access

- **OWNER**:
  - Can create, view, update, and delete their own shops
  - Can assign managers to shops
  - Sees all shops they own
  - Can access CCTV streams for their shops

- **MANAGER**:
  - Can only view shops they're assigned to
  - Cannot create or delete shops
  - Can access CCTV streams for assigned shops only

---

## Environment Setup

### Install Dependencies

```bash
npm install axios react-router-dom
# OR
yarn add axios react-router-dom
```

### Environment Variables

Create a `.env` or `.env.local` file:

```env
# API Base URL
REACT_APP_API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000  # For Next.js

# WebSocket URL
REACT_APP_WS_URL=ws://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Authentication Context & State Management

### Create Auth Context (`src/context/AuthContext.jsx`)

```jsx
import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [loading, setLoading] = useState(true);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Load tokens from localStorage on mount
  useEffect(() => {
    const storedAccessToken = localStorage.getItem('access_token');
    const storedRefreshToken = localStorage.getItem('refresh_token');
    const storedUser = localStorage.getItem('user');

    if (storedAccessToken && storedUser) {
      setAccessToken(storedAccessToken);
      setRefreshToken(storedRefreshToken);
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  // Register new owner
  const registerOwner = async (name, email, password) => {
    try {
      const response = await axios.post(`${API_URL}/auth/register-owner`, {
        name,
        email,
        password,
      });

      const { access_token, refresh_token, user: userData } = response.data;

      // Store tokens and user data
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.setItem('user', JSON.stringify(userData));

      setAccessToken(access_token);
      setRefreshToken(refresh_token);
      setUser(userData);

      return { success: true, user: userData };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed',
      };
    }
  };

  // Login
  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        email,
        password,
      });

      const { access_token, refresh_token, user: userData } = response.data;

      // Store tokens and user data
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.setItem('user', JSON.stringify(userData));

      setAccessToken(access_token);
      setRefreshToken(refresh_token);
      setUser(userData);

      return { success: true, user: userData };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed',
      };
    }
  };

  // Logout
  const logout = async () => {
    try {
      // Optional: Call backend logout endpoint
      if (accessToken) {
        await axios.post(
          `${API_URL}/auth/logout`,
          {},
          {
            headers: { Authorization: `Bearer ${accessToken}` },
          }
        );
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');

      setAccessToken(null);
      setRefreshToken(null);
      setUser(null);
    }
  };

  // Get current user info
  const getCurrentUser = async () => {
    if (!accessToken) return null;

    try {
      const response = await axios.get(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      return response.data;
    } catch (error) {
      console.error('Get current user error:', error);
      return null;
    }
  };

  const value = {
    user,
    accessToken,
    refreshToken,
    loading,
    isAuthenticated: !!accessToken,
    isOwner: user?.role === 'OWNER',
    isManager: user?.role === 'MANAGER',
    registerOwner,
    login,
    logout,
    getCurrentUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

---

## API Client Setup

### Create Axios Instance (`src/api/axios.js`)

```javascript
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## Authentication Components

### Login Component (`src/components/Login.jsx`)

```jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);

    if (result.success) {
      // Redirect based on role
      if (result.user.role === 'OWNER') {
        navigate('/dashboard');
      } else {
        navigate('/my-shops');
      }
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="login-container">
      <h2>Login to VisionGuard AI</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Email:</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label>Password:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <div className="error-message">{error}</div>}

        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>

      <p>
        Don't have an account? <a href="/register">Register as Owner</a>
      </p>
    </div>
  );
};

export default Login;
```

### Register Component (`src/components/Register.jsx`)

```jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Register = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { registerOwner } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);

    const result = await registerOwner(name, email, password);

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="register-container">
      <h2>Register as Shop Owner</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Full Name:</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label>Email:</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label>Password:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label>Confirm Password:</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        </div>

        {error && <div className="error-message">{error}</div>}

        <button type="submit" disabled={loading}>
          {loading ? 'Registering...' : 'Register'}
        </button>
      </form>

      <p>
        Already have an account? <a href="/login">Login</a>
      </p>
    </div>
  );
};

export default Register;
```

---

## Protected Routes

### Protected Route Component (`src/components/ProtectedRoute.jsx`)

```jsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ children, requireRole = null }) => {
  const { isAuthenticated, user, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireRole && user?.role !== requireRole) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

export default ProtectedRoute;
```

### App Router Setup (`src/App.jsx`)

```jsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';
import ShopList from './components/ShopList';
import VideoStream from './components/VideoStream';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Owner-only routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute requireRole="OWNER">
                <Dashboard />
              </ProtectedRoute>
            }
          />

          {/* Routes for both OWNER and MANAGER */}
          <Route
            path="/my-shops"
            element={
              <ProtectedRoute>
                <ShopList />
              </ProtectedRoute>
            }
          />

          <Route
            path="/shop/:shopId/stream"
            element={
              <ProtectedRoute>
                <VideoStream />
              </ProtectedRoute>
            }
          />

          <Route path="/" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
```

---

## Shop Management

### Shop API Service (`src/api/shopService.js`)

```javascript
import apiClient from './axios';

export const shopService = {
  // Get all shops (OWNER sees owned, MANAGER sees assigned)
  getAllShops: async () => {
    const response = await apiClient.get('/shops');
    return response.data;
  },

  // Get specific shop
  getShop: async (shopId) => {
    const response = await apiClient.get(`/shops/${shopId}`);
    return response.data;
  },

  // Create shop (OWNER only)
  createShop: async (shopData) => {
    const response = await apiClient.post('/shops', shopData);
    return response.data;
  },

  // Update shop (OWNER only)
  updateShop: async (shopId, shopData) => {
    const response = await apiClient.put(`/shops/${shopId}`, shopData);
    return response.data;
  },

  // Delete shop (OWNER only)
  deleteShop: async (shopId) => {
    await apiClient.delete(`/shops/${shopId}`);
  },

  // Get shop managers
  getShopManagers: async (shopId) => {
    const response = await apiClient.get(`/shops/${shopId}/managers`);
    return response.data;
  },
};
```

### Shop List Component (`src/components/ShopList.jsx`)

```jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { shopService } from '../api/shopService';

const ShopList = () => {
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const { user, isOwner } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    loadShops();
  }, []);

  const loadShops = async () => {
    try {
      const data = await shopService.getAllShops();
      setShops(data);
    } catch (err) {
      setError('Failed to load shops');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleViewStream = (shopId) => {
    navigate(`/shop/${shopId}/stream`);
  };

  if (loading) return <div>Loading shops...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="shop-list">
      <h2>{isOwner ? 'My Shops' : 'Assigned Shops'}</h2>

      {isOwner && (
        <button onClick={() => navigate('/create-shop')}>
          Create New Shop
        </button>
      )}

      <div className="shops-grid">
        {shops.map((shop) => (
          <div key={shop.id} className="shop-card">
            <h3>{shop.name}</h3>
            <p>{shop.address}</p>
            
            <div className="managers">
              <strong>Managers:</strong>
              {shop.managers.length > 0 ? (
                <ul>
                  {shop.managers.map((manager) => (
                    <li key={manager.id}>{manager.email}</li>
                  ))}
                </ul>
              ) : (
                <p>No managers assigned</p>
              )}
            </div>

            <button onClick={() => handleViewStream(shop.id)}>
              View CCTV Stream
            </button>

            {isOwner && (
              <button onClick={() => navigate(`/shop/${shop.id}/edit`)}>
                Edit Shop
              </button>
            )}
          </div>
        ))}
      </div>

      {shops.length === 0 && (
        <p>No shops available. {isOwner && 'Create your first shop!'}</p>
      )}
    </div>
  );
};

export default ShopList;
```

---

## WebRTC Integration with Auth

### Video Stream Component with Authentication (`src/components/VideoStream.jsx`)

```jsx
import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const VideoStream = () => {
  const { shopId } = useParams();
  const { user, accessToken } = useAuth();
  const videoRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const [streamId, setStreamId] = useState(null);
  const [error, setError] = useState('');

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    startWebRTC();

    return () => {
      // Cleanup
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
    };
  }, [shopId]);

  const startWebRTC = async () => {
    try {
      // Get user media (camera)
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: false,
      });

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      // Create RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
        ],
      });

      peerConnectionRef.current = pc;

      // Add video track to peer connection
      stream.getTracks().forEach((track) => {
        pc.addTrack(track, stream);
      });

      // Create and send offer to backend
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Send offer to backend with authentication
      const response = await fetch(`${API_URL}/api/offer`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          sdp: offer.sdp,
          type: offer.type,
          user_id: user.id,
          shop_id: shopId,
          stream_metadata: {
            stream_name: 'CCTV Camera 1',
            camera_id: 'cam-001',
            location: 'Entrance',
          },
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to connect');
      }

      const answer = await response.json();
      setStreamId(answer.stream_id);

      // Set remote description (answer from server)
      await pc.setRemoteDescription(
        new RTCSessionDescription({
          sdp: answer.sdp,
          type: answer.type,
        })
      );

      console.log('WebRTC connection established');
    } catch (err) {
      console.error('WebRTC error:', err);
      setError(err.message);
    }
  };

  return (
    <div className="video-stream">
      <h2>CCTV Stream - Shop ID: {shopId}</h2>
      {streamId && <p>Stream ID: {streamId}</p>}

      {error && <div className="error">{error}</div>}

      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ width: '100%', maxWidth: '640px' }}
      />
    </div>
  );
};

export default VideoStream;
```

---

## WebSocket Integration with Auth

### WebSocket Anomaly Alerts (`src/hooks/useAnomalyAlerts.js`)

```javascript
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const useAnomalyAlerts = () => {
  const { user, accessToken } = useAuth();
  const wsRef = useRef(null);
  const [alerts, setAlerts] = useState([]);
  const [connected, setConnected] = useState(false);

  const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

  useEffect(() => {
    if (!user || !accessToken) return;

    // Connect to WebSocket with authentication
    const ws = new WebSocket(
      `${WS_URL}/ws/alerts/${user.id}?token=${accessToken}`
    );

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'anomaly_detected') {
        console.log('Anomaly detected:', data);
        
        // Add to alerts list
        setAlerts((prev) => [
          {
            id: Date.now(),
            stream_id: data.stream_id,
            person_id: data.result.person_id,
            timestamp: new Date().toISOString(),
            frame: data.annotated_frame,
            details: data.result,
          },
          ...prev,
        ]);

        // Send acknowledgment
        ws.send(
          JSON.stringify({
            type: 'ack',
            stream_id: data.stream_id,
          })
        );
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    wsRef.current = ws;

    // Cleanup
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [user, accessToken]);

  const clearAlerts = () => {
    setAlerts([]);
  };

  return { alerts, connected, clearAlerts };
};
```

### Anomaly Alerts Component (`src/components/AnomalyAlerts.jsx`)

```jsx
import React from 'react';
import { useAnomalyAlerts } from '../hooks/useAnomalyAlerts';

const AnomalyAlerts = () => {
  const { alerts, connected, clearAlerts } = useAnomalyAlerts();

  return (
    <div className="anomaly-alerts">
      <div className="alerts-header">
        <h3>Anomaly Alerts</h3>
        <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '● Connected' : '○ Disconnected'}
        </span>
        {alerts.length > 0 && (
          <button onClick={clearAlerts}>Clear All</button>
        )}
      </div>

      <div className="alerts-list">
        {alerts.length === 0 ? (
          <p>No anomalies detected</p>
        ) : (
          alerts.map((alert) => (
            <div key={alert.id} className="alert-card">
              <div className="alert-info">
                <strong>Person #{alert.person_id}</strong>
                <span>{new Date(alert.timestamp).toLocaleTimeString()}</span>
              </div>

              <div className="alert-details">
                <p>Stream: {alert.stream_id}</p>
                <p>Status: {alert.details.status}</p>
              </div>

              {alert.frame && (
                <img
                  src={`data:image/jpeg;base64,${alert.frame}`}
                  alt="Anomaly detected"
                  className="alert-frame"
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AnomalyAlerts;
```

---

## Complete Code Examples

### Create Shop Form (`src/components/CreateShop.jsx`)

```jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { shopService } from '../api/shopService';

const CreateShop = () => {
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [managerEmails, setManagerEmails] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Parse comma-separated emails
      const emailList = managerEmails
        .split(',')
        .map((email) => email.trim())
        .filter((email) => email);

      await shopService.createShop({
        name,
        address,
        assigned_manager_emails: emailList,
      });

      navigate('/my-shops');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create shop');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="create-shop">
      <h2>Create New Shop</h2>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Shop Name:</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label>Address:</label>
          <textarea
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            rows={3}
          />
        </div>

        <div className="form-group">
          <label>Manager Emails (comma-separated):</label>
          <input
            type="text"
            value={managerEmails}
            onChange={(e) => setManagerEmails(e.target.value)}
            placeholder="manager1@example.com, manager2@example.com"
          />
          <small>
            Leave empty for no managers. New accounts will be created
            automatically.
          </small>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="form-actions">
          <button type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Create Shop'}
          </button>
          <button type="button" onClick={() => navigate('/my-shops')}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default CreateShop;
```

---

## Security Best Practices

### 1. Token Storage

```javascript
// Option 1: localStorage (survives page refresh)
localStorage.setItem('access_token', token);

// Option 2: sessionStorage (cleared on tab close)
sessionStorage.setItem('access_token', token);

// Option 3: Memory only (most secure, lost on refresh)
// Store in React state/context only
```

### 2. Automatic Token Refresh (Future Enhancement)

```javascript
// In your API client
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post('/auth/refresh', {
          refresh_token: refreshToken,
        });

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed, logout user
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

### 3. HTTPS Only in Production

```javascript
// Ensure WebSocket uses wss:// in production
const WS_URL =
  process.env.NODE_ENV === 'production'
    ? 'wss://your-domain.com'
    : 'ws://localhost:8000';
```

---

## Testing the Integration

### 1. Test Authentication Flow

```bash
# Register as owner
curl -X POST http://localhost:8000/auth/register-owner \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","email":"john@example.com","password":"password123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"password123"}'
```

### 2. Test Shop Creation

```bash
# Create shop (use token from login response)
curl -X POST http://localhost:8000/shops \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"name":"My Shop","address":"123 Main St","assigned_manager_emails":["manager@example.com"]}'
```

### 3. Test WebSocket Connection

```javascript
// In browser console
const ws = new WebSocket(
  'ws://localhost:8000/ws/alerts/YOUR_USER_ID?token=YOUR_ACCESS_TOKEN'
);
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
```

---

## Troubleshooting

### Common Issues

1. **401 Unauthorized on Protected Endpoints**
   - Check token is included in Authorization header
   - Verify token hasn't expired
   - Ensure user has correct permissions

2. **WebSocket Connection Fails**
   - Verify token is passed as query parameter
   - Check CORS settings allow WebSocket connections
   - Ensure user_id matches authenticated user

3. **403 Forbidden on Shop Access**
   - Verify user owns the shop (OWNER) or is assigned (MANAGER)
   - Check shop_id is valid UUID format

---

## Summary

This guide covers:
✅ Complete authentication flow (register, login, logout)
✅ JWT token management
✅ Protected routes and role-based access
✅ Shop CRUD operations with manager assignment
✅ WebRTC integration with authentication
✅ WebSocket connection with JWT token
✅ Real-world React components

Your frontend is now ready to integrate with the VisionGuard AI authentication system!
