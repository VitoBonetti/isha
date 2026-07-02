import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'pentester' | 'read_only';
  location_id: string;
  avatar_url: string | null;
}

interface AppContextType {
  currentUser: User | null;
  isLoading: boolean;
  handleLogout: () => Promise<void>;
  wsStatus: 'connecting' | 'connected' | 'disconnected';
  notifications: any[];
  showNotifications: boolean;
  setShowNotifications: (val: boolean) => void;
  markNotificationsRead: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // App State
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  const navigate = useNavigate();

  const fetchNotifications = async () => {
    try {
      const res = await axios.get('/api/users/me/notifications');
      setNotifications(res.data);
    } catch (e) {
      console.error("Failed to fetch notifications");
    }
  };

  const markNotificationsRead = async () => {
    try {
      await axios.put('/api/users/me/notifications/read');
      setNotifications([]);
      setShowNotifications(false);
    } catch (e) {
      console.error("Failed to mark read");
    }
  };

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await axios.get('/api/users/me');
        setCurrentUser(res.data);
      } catch (err) {
        setCurrentUser(null);
        navigate('/login');
      } finally {
        setIsLoading(false);
      }
    };
    fetchUser();
  }, [navigate]);

  useEffect(() => {
    if (currentUser) fetchNotifications();
  }, [currentUser]);

  // WebSocket Connection
  useEffect(() => {
    if (!currentUser) return;

    let ws: WebSocket;
    let reconnectTimer: number;

    const connectWebSocket = () => {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;

      ws = new WebSocket(`${wsProtocol}//${host}/ws/board`);

      ws.onopen = () => setWsStatus('connected');

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.action === 'REFRESH_BOARD' || data.action === 'REFRESH_ASSETS') {
          fetchNotifications();
        }
      };

      ws.onclose = (event) => {
        setWsStatus('disconnected');
        if (event.code === 1008) {
          setCurrentUser(null);
          navigate('/login');
        } else {
          reconnectTimer = window.setTimeout(connectWebSocket, 3000);
        }
      };

      ws.onerror = () => ws.close();
    };

    connectWebSocket();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close(1000, "Unmounting");
    };
  }, [currentUser, navigate]);

  const handleLogout = async () => {
    try {
      await axios.post('/api/auth/logout');
    } catch (err) {
      console.error("Logout failed", err);
    } finally {
      setCurrentUser(null);
      navigate('/login');
    }
  };

  return (
    <AppContext.Provider value={{
      currentUser, isLoading, handleLogout,
      wsStatus, notifications, showNotifications, setShowNotifications, markNotificationsRead
    }}>
      {children}
    </AppContext.Provider>
  );
}

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};