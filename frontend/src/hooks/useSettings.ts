import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';

export function useSettings() {
  const [activeTab, setActiveTab] = useState('users');

  const [users, setUsers] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [regions, setRegions] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);
  const [dbLatency, setDbLatency] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchAllData = useCallback(async (isBackground = false) => {
    if (!isBackground) setIsLoading(true);
    try {
      const [
        resUsers, resLocations, resServices,
        resCategories, resRegions, resCountries, resLogs, resPing, resAssetTypes
      ] = await Promise.all([
        axios.get('/api/users/').catch(() => ({ data: [] })),
        axios.get('/api/locations/').catch(() => ({ data: [] })),
        axios.get('/api/services/').catch(() => ({ data: [] })),
        axios.get('/api/board/categories/').catch(() => ({ data: [] })),
        axios.get('/api/regions/').catch(() => ({ data: [] })),
        axios.get('/api/countries/').catch(() => ({ data: [] })),
        axios.get('/api/system/logs/').catch(() => ({ data: { files: [] } })),
        axios.get('/api/system/ping').catch(() => ({ data: { latency_ms: null } })),
        axios.get('/api/assets/types').catch(() => ({ data: [] }))
      ]);

      setUsers(resUsers.data || []);
      setLocations(resLocations.data || []);
      setServices(resServices.data || []);
      setCategories(resCategories.data || []);
      setRegions(resRegions.data || []);
      setCountries(resCountries.data || []);
      setLogs(resLogs.data.files || []);
      setDbLatency(resPing.data.latency_ms);
      setAssetTypes(resAssetTypes.data || []);

    } catch (error) {
      toast.error('Failed to load settings data');
    } finally {
      if (!isBackground) setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAllData(false); }, [fetchAllData]);

  const handleSave = async (endpoint: string, payload: any, isUpdate: boolean, id?: string) => {
    try {
      if (isUpdate && id) {
        await axios.put(`${endpoint}${id}`, payload);
        toast.success('Updated successfully');
      } else {
        await axios.post(endpoint, payload);
        toast.success('Created successfully');
      }
      fetchAllData(true);
      return true;
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Operation failed');
      return false;
    }
  };

  const handleDelete = async (endpoint: string, id: string) => {
    try {
      await axios.delete(`${endpoint}${id}`);
      toast.success('Deleted successfully');
      fetchAllData(true);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to delete');
    }
  };

  const downloadLog = async (filename: string) => {
    try {
      const response = await axios.get(`/api/system/logs/${filename}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (error) { toast.error('Failed to download log'); }
  };

  const handleWipeSystem = async () => {
    try {
      await axios.delete('/api/danger/system/wipe');
      toast.success('System data wiped successfully.');
      fetchAllData(true);
    } catch (error) { toast.error('Failed to wipe system.'); }
  };

  // MUST return dbLatency here
  return { activeTab, setActiveTab, users, locations, services, categories, regions, countries, logs, dbLatency, isLoading, assetTypes, handleSave, handleDelete, downloadLog, handleWipeSystem };
}