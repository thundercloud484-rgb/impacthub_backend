"use client";
import { useEffect, useState } from "react";
import { adminService } from "@/services/admin.service";
import { Users, FileText, Calendar, TrendingUp } from "lucide-react";
import toast from "react-hot-toast";

interface Stats {
  total_users: number;
  active_users: number;
  total_posts: number;
  total_events: number;
}


export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const { data } = await adminService.getStats();
      setStats(data.stats);
    } catch (err) {
      toast.error("Failed to load stats");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const cards = [
    {
      title: "Total Users",
      value: stats?.total_users || 0,
      subtitle: `${stats?.active_users || 0} active`,
      icon: Users,
      color: "bg-blue-500",
    },
    {
      title: "Total Posts",
      value: stats?.total_posts || 0,
      subtitle: "All time",
      icon: FileText,
      color: "bg-green-500",
    },
    {
      title: "Total Events",
      value: stats?.total_events || 0,
      subtitle: "All time",
      icon: Calendar,
      color: "bg-purple-500",
    },
    {
      title: "Active Users",
      value: stats?.active_users || 0,
      subtitle: `${Math.round(((stats?.active_users || 0) / (stats?.total_users || 1)) * 100)}% of total`,
      icon: TrendingUp,
      color: "bg-amber-500",
    },
  ];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-600 mt-1">Overview of your platform</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.title}
              className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 ${card.color} rounded-lg flex items-center justify-center`}>
                  <Icon className="h-6 w-6 text-white" />
                </div>
              </div>
              <h3 className="text-sm font-medium text-slate-600 mb-1">{card.title}</h3>
              <p className="text-3xl font-bold text-slate-900 mb-1">{card.value.toLocaleString()}</p>
              <p className="text-xs text-slate-500">{card.subtitle}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-8 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/admin/users"
            className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <Users className="h-6 w-6 text-slate-600 mb-2" />
            <h3 className="font-semibold text-slate-900">Manage Users</h3>
            <p className="text-sm text-slate-600 mt-1">View and moderate user accounts</p>
          </a>
          <a
            href="/admin/posts"
            className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <FileText className="h-6 w-6 text-slate-600 mb-2" />
            <h3 className="font-semibold text-slate-900">Manage Posts</h3>
            <p className="text-sm text-slate-600 mt-1">Review and moderate content</p>
          </a>
          <a
            href="/admin/events"
            className="p-4 border border-slate-200 rounded-lg hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <Calendar className="h-6 w-6 text-slate-600 mb-2" />
            <h3 className="font-semibold text-slate-900">Manage Events</h3>
            <p className="text-sm text-slate-600 mt-1">Oversee community events</p>
          </a>
        </div>
      </div>

    </div>
  );
}
