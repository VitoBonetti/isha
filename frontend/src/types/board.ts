export interface Pentester {
  id: string;
  name: string;
  role: string;
  email: string;
  capacity: number;
  location_id: string;
  start_year?: number;
  start_week?: number;
  end_year?: number;
  end_week?: number;
}

export interface ServiceLane {
  id: string;
  name: string;
  theme_color: string;
  is_active?: boolean;
  max_concurrent_per_week?: number;
  display_order?: number;
  auto_provision_workspace?: boolean;
}

export interface Test {
  id: string;
  name: string;
  service_lane_id: string;
  category_id?: string;
  credits: number;
  duration: number;
  startWeek?: number;
  startYear?: number;
  status: 'Not Planned' | 'Scheduled' | 'In Progress' | 'Stopped' | 'Deleted' | 'Completed' | 'Archived';
  asset_count: number;
  has_secret?: boolean;
  is_service_active?: boolean;
  drive_folder_id?: string;
  drive_folder_url?: string;
  auto_provision_workspace?: boolean;
  is_tentative?: boolean;
}

export interface Assignment {
  test_id: string;
  user_id: string;
  week_number: number;
  user_name: string;
  allocated_credits: number;
}

export interface BoardData {
  year: number;
  quarter: number;
  weeks: number[];
  services: ServiceLane[];
  pentesters: Pentester[];
  capacities: Record<string, Record<number, number>>;
  backlog: Test[];
  scheduled: Test[];
  assignments: Assignment[];
  events: any[];
}