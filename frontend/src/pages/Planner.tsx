import { useState, useEffect, useRef } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import type { DropResult } from '@hello-pangea/dnd';
import PlannerView from "./PlannerView";
import ConfirmModal from "../components/Modals/ConfirmModal";
import EditTestModal from "../components/Modals/EditTestModal";
import type { BoardData, Test } from "../types/board";

export default function Planner() {
  const [boardData, setBoardData] = useState<BoardData | null>(null);

  // Time state
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());
  const [targetQuarter, setTargetQuarter] = useState(() => {
    const month = new Date().getMonth() + 1;
    if (month > 9) return 4;
    if (month > 6) return 3;
    if (month > 3) return 2;
    return 1;
  });

  const [assignModalTest, setAssignModalTest] = useState<Test | null>(null);
  const [backlogFilter, setBacklogFilter] = useState("All");

  // Modal States
  const [editModalTest, setEditModalTest] = useState<Test | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    action: (() => Promise<void>) | null;
  }>({ isOpen: false, title: "", message: "", action: null });

  // --- MULTIPLAYER & WEBSOCKET STATE ---
  const [onlineUsers, setOnlineUsers] = useState<string[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchBoardData();

    // 1. Establish WebSocket connection automatically
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/board`;

    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      console.log("🟢 Connected to live board synchronization");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // 2. Listen for Database Changes
        if (data.action === 'REFRESH_BOARD') {
          fetchBoardData();

          // Dispatch a global event so your TopNav knows to re-fetch notifications!
          window.dispatchEvent(new CustomEvent('refresh_notifications'));
        }
        // 3. Listen for User Presence (Other admins opening the page)
        else if (data.action === 'ONLINE_USERS' && data.users) {
          setOnlineUsers(data.users);
        }
      } catch (e) {
        console.error("WebSocket message error:", e);
      }
    };

    socket.onclose = () => {
      console.log("🔴 Disconnected from live board");
    };

    return () => {
      socket.close();
    };
  }, [targetYear, targetQuarter]);

  const fetchBoardData = async () => {
    try {
      const res = await axios.get(`/api/board/${targetYear}/Q${targetQuarter}`);
      setBoardData(res.data);
    } catch (error) {
      console.error("Failed to fetch board data", error);
      toast.error("Failed to sync with server.");
    }
  };

  // --- TIME NAVIGATION ---
  const handlePrevQuarter = () => {
    if (targetQuarter === 1) { setTargetQuarter(4); setTargetYear(y => y - 1); }
    else { setTargetQuarter(q => q - 1); }
  };

  const handleNextQuarter = () => {
    if (targetQuarter === 4) { setTargetQuarter(1); setTargetYear(y => y + 1); }
    else { setTargetQuarter(q => q + 1); }
  };

  const handleCurrentQuarter = () => {
    setTargetYear(new Date().getFullYear());
    const month = new Date().getMonth() + 1;
    setTargetQuarter(month > 9 ? 4 : month > 6 ? 3 : month > 3 ? 2 : 1);
  };

  // --- DRAG AND DROP HANDLER ---
  const onDragEnd = async (result: DropResult) => {
    const { destination, source, draggableId } = result;

    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) return;

    try {
      if (destination.droppableId !== 'backlog') {
        const [serviceId, weekStr] = destination.droppableId.split('_');
        const week = parseInt(weekStr, 10);

        await axios.put(`/api/tests/${draggableId}/schedule`, {
          start_week: week,
          start_year: targetYear
        });
        toast.success("Test scheduled!");
      }
      else if (destination.droppableId === 'backlog' && source.droppableId !== 'backlog') {
        await axios.put(`/api/tests/${draggableId}/unschedule`);
        toast.success("Test returned to backlog.");
      }
      // Note: We don't strictly need fetchBoardData() here anymore because the backend
      // will broadcast 'REFRESH_BOARD' and trigger it for everyone, including us!
    } catch (error) {
      console.error("Failed to move test:", error);
      toast.error("Failed to move test.");
    }
  };

  // --- ACTION BUTTON HANDLERS ---
  const handleCompleteTest = async (testId: string) => {
    try {
      await axios.put(`/api/tests/${testId}/complete`);
      toast.success("Test marked as Completed!");
    } catch (error) { toast.error("Failed to complete test."); }
  };

  const handleUnscheduleTest = async (testId: string) => {
    try {
      await axios.put(`/api/tests/${testId}/unschedule`);
      toast.success("Test unscheduled and returned to backlog.");
    } catch (error) { toast.error("Failed to unschedule test."); }
  };

  const handleMarkUnable = (testId: string) => {
    setConfirmModal({
      isOpen: true,
      title: "Stop Test?",
      message: "Mark this test as Stopped? This will leave a record of burned capacity and return the original test to the backlog.",
      action: async () => {
        try {
          await axios.put(`/api/tests/${testId}/unable`);
          toast.success("Test stopped. Original returned to backlog.");
        } catch (error) { toast.error("Failed to stop test."); }
      }
    });
  };

  const handleDeleteTest = (testId: string) => {
    setConfirmModal({
      isOpen: true,
      title: "Permanently Delete Test?",
      message: "Are you sure you want to delete this test? This will free the attached assets back to the active pool.",
      action: async () => {
        try {
          await axios.delete(`/api/tests/${testId}`);
          toast.success("Test permanently deleted.");
        } catch (error) { toast.error("Failed to delete test."); }
      }
    });
  };

  const handleAssignTeam = async (userId: string) => {
    if (!assignModalTest || !boardData) return;

    try {
      const startWk = assignModalTest.startWeek || 1;
      const startYr = assignModalTest.startYear || targetYear;
      const duration = assignModalTest.duration || 1;

      const assignmentPromises = [];
      let totalAssignedCredits = 0;

      for (let i = 0; i < duration; i++) {
        let assignWeek = startWk + i;
        let assignYear = startYr;

        if (assignWeek > 52) {
          assignWeek -= 52;
          assignYear += 1;
        }

        // --- NEW: Grab the REAL available capacity from the board data ---
        const realCapacity = boardData.capacities[userId]?.[assignWeek] || 0;

        // Only assign them to the week if they actually have capacity > 0
        if (realCapacity > 0) {
          totalAssignedCredits += realCapacity;
          assignmentPromises.push(
            axios.post('/api/tests/assignments', {
              test_id: assignModalTest.id,
              user_id: userId,
              week_number: assignWeek,
              year: assignYear,
              allocated_credits: realCapacity // <-- Dynamic Assignment!
            })
          );
        }
      }

      if (assignmentPromises.length === 0) {
        toast.error("User has no available capacity for the selected weeks.");
        return;
      }

      await Promise.all(assignmentPromises);
      toast.success(`Assigned with ${totalAssignedCredits.toFixed(1)} total credits!`);
      setAssignModalTest(null);
    } catch (error: any) {
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error("Failed to assign pentester.");
      }
    }
  };

  const handleUnassignPentester = async (testId: string, userId: string) => {
    try {
      await axios.delete(`/api/tests/assignments/${testId}/${userId}`);
      toast.success("Pentester removed from test.");
    } catch (error) { toast.error("Failed to remove pentester."); }
  };

  // --- REVERT BUTTONS ---
  const handleRevertComplete = async (testId: string) => {
    try {
      await axios.put(`/api/tests/${testId}/uncomplete`);
      toast.success("Test reverted to Scheduled.");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to revert status.");
    }
  };

  const handleRevertUnable = async (testId: string) => {
    try {
      await axios.put(`/api/tests/${testId}/unstop`);
      toast.success("Test unblocked!");
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to unblock test.");
    }
  };

  const handleUpdateTest = async (testId: string, updatedData: any) => {
    try {
      await axios.put(`/api/tests/${testId}`, updatedData);
      toast.success("Test settings updated!");
      setEditModalTest(null);
    } catch (error) {
      console.error(error);
      toast.error("Failed to update test.");
    }
  };

  const handleDuplicateTest = (testId: string) => console.log("Duplicate Triggered:", testId);

  return (
    <>
      <PlannerView
        onlineUsers={onlineUsers}
        targetYear={targetYear}
        targetQuarter={targetQuarter}
        handlePrevQuarter={handlePrevQuarter}
        handleNextQuarter={handleNextQuarter}
        handleCurrentQuarter={handleCurrentQuarter}
        boardData={boardData}
        setNewTest={() => {}}
        setShowTestForm={() => {}}
        onDragEnd={onDragEnd}
        handleAssignTeam={handleAssignTeam}
        handleCompleteTest={handleCompleteTest}
        handleUnscheduleTest={handleUnscheduleTest}
        handleUnassignPentester={handleUnassignPentester}
        handleDeleteTest={handleDeleteTest}
        handleDuplicateTest={handleDuplicateTest}
        openEditModal={(test) => setEditModalTest(test)}
        handleMarkUnable={handleMarkUnable}
        handleRevertComplete={handleRevertComplete}
        handleRevertUnable={handleRevertUnable}
        assignModalTest={assignModalTest}
        setAssignModalTest={setAssignModalTest}
        backlogFilter={backlogFilter}
        setBacklogFilter={setBacklogFilter}
      />

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        onCancel={() => setConfirmModal({ ...confirmModal, isOpen: false })}
        onConfirm={async () => {
          if (confirmModal.action) await confirmModal.action();
          setConfirmModal({ ...confirmModal, isOpen: false });
        }}
      />

      <EditTestModal
        isOpen={!!editModalTest}
        test={editModalTest}
        boardData={boardData}
        onClose={() => setEditModalTest(null)}
        onSubmit={handleUpdateTest}
      />
    </>
  );
}