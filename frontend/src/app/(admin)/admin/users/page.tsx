"use client";
import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { adminService } from "@/services/admin.service";
import { Search, Ban, CheckCircle, Trash2, Shield, User, Key, TrendingUp, X, Building2, Globe2 } from "lucide-react";
import toast from "react-hot-toast";

interface UserData {
  id: string;
  name: string;
  username: string;
  email: string;
  avatar: { url: string };
  category: string;
  role: string;
  is_active: boolean;
  followers_count: number;
  posts_count: number;
  impact_score: number;
  created_at: string;
}

interface GroupData {
  id: string;
  name: string;
  slug: string;
  description?: string;
  is_official?: boolean;
  is_community?: boolean;
  is_active?: boolean;
  member_count?: number;
  total_points?: number;
}

type AdminTab = "users" | "hubs" | "official" | "communities" | "authorities";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [groups, setGroups] = useState<GroupData[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<Set<string>>(new Set());
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Points management state
  const [showPointsModal, setShowPointsModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserData | null>(null);
  const [pointsAdjustment, setPointsAdjustment] = useState<number>(0);
  const [adjustmentReason, setAdjustmentReason] = useState("");
  const [impactLog, setImpactLog] = useState<any[]>([]);
  const [loadingLog, setLoadingLog] = useState(false);

  useEffect(() => {
    if (activeTab === "users" || activeTab === "authorities") {
      loadUsers();
    }
  }, [page, search, activeTab]);

  useEffect(() => {
    if (activeTab === "hubs" || activeTab === "official" || activeTab === "communities") {
      loadGroups();
    }
  }, [activeTab]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const role = activeTab === "authorities" ? "authority" : "user";
      const { data } = await adminService.getUsers(page, 20, search || undefined, role);
      setUsers(data.users);
      setTotalPages(data.pagination.pages);
    } catch (err) {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const loadGroups = async () => {
    setLoading(true);
    try {
      const { data } = await adminService.getGroups();
      setGroups(
        (data.groups || []).filter((group: GroupData) =>
          activeTab === "communities"
            ? group.is_community
            : activeTab === "official"
              ? group.is_official && !group.is_community
              : !group.is_community && !group.is_official
        )
      );
    } catch (err) {
      toast.error("Failed to load groups");
    } finally {
      setLoading(false);
    }
  };

  const selectTab = (tab: AdminTab) => {
    setActiveTab(tab);
    setPage(1);
    setSearch("");
    setSelectedUsers(new Set());
    setSelectedGroups(new Set());
  };

  const toggleSelected = (
    id: string,
    setter: Dispatch<SetStateAction<Set<string>>>
  ) => {
    setter((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDeleteSelectedUsers = async () => {
    if (selectedUsers.size === 0) return;
    if (!confirm(`Permanently delete ${selectedUsers.size} selected users? This cannot be undone.`)) return;
    try {
      const { data } = await adminService.deleteUsers(Array.from(selectedUsers));
      setUsers(users.filter((user) => !selectedUsers.has(user.id)));
      setSelectedUsers(new Set());
      toast.success(`${data.deleted_count} users deleted`);
      if (data.skipped_users?.length) {
        toast.error(`${data.skipped_users.length} users were skipped`);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to delete selected users");
    }
  };

  const handleDeleteSelectedGroups = async () => {
    if (selectedGroups.size === 0) return;
    if (!confirm(`Permanently delete ${selectedGroups.size} selected groups? This cannot be undone.`)) return;
    try {
      const { data } = await adminService.deleteGroups(Array.from(selectedGroups));
      setGroups(groups.filter((group) => !selectedGroups.has(group.id)));
      setSelectedGroups(new Set());
      toast.success(`${data.deleted_count} groups deleted`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to delete selected groups");
    }
  };

  const handleDeleteGroup = async (group: GroupData) => {
    if (!confirm(`Permanently delete "${group.name}"? This removes its members and messages.`)) return;
    try {
      await adminService.deleteGroup(group.id);
      setGroups(groups.filter((item) => item.id !== group.id));
      toast.success("Group deleted");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to delete group");
    }
  };

  const handleToggleGroupActive = async (group: GroupData) => {
    try {
      const { data } = await adminService.toggleGroupActive(group.id);
      setGroups(groups.map((item) =>
        item.id === group.id ? { ...item, is_active: data.group.is_active } : item
      ));
      toast.success(data.group.is_active ? "Group activated" : "Group deactivated");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update group");
    }
  };

  const handleToggleActive = async (userId: string) => {
    try {
      const { data } = await adminService.toggleUserActive(userId);
      setUsers(users.map((u) => (u.id === userId ? data.user : u)));
      toast.success(data.user.is_active ? "User activated" : "User deactivated");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update user");
    }
  };

  const handleToggleRole = async (userId: string, currentRole: string) => {
    const newRole = currentRole === "admin" ? "user" : "admin";
    if (!confirm(`Change user role to ${newRole}?`)) return;

    try {
      const { data } = await adminService.updateUserRole(userId, newRole);
      setUsers(users.map((u) => (u.id === userId ? data.user : u)));
      toast.success(`Role updated to ${newRole}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update role");
    }
  };

  const handleDelete = async (userId: string, username: string) => {
    if (!confirm(`Permanently delete user @${username}? This removes their account and content.`)) return;

    try {
      await adminService.deleteUser(userId);
      setUsers(users.filter((u) => u.id !== userId));
      toast.success("User deleted");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to delete user");
    }
  };

  const handleResetPassword = async (userId: string, username: string) => {
    const newPassword = prompt(`Enter new password for @${username}:\n(Minimum 8 characters)`);
    if (!newPassword) return;
    
    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    try {
      await adminService.resetUserPassword(userId, newPassword);
      toast.success("Password reset successfully");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to reset password");
    }
  };

  const openPointsModal = async (user: UserData) => {
    setSelectedUser(user);
    setShowPointsModal(true);
    setPointsAdjustment(0);
    setAdjustmentReason("");
    
    // Load impact log
    setLoadingLog(true);
    try {
      const { data } = await adminService.getUserImpactLog(user.id);
      setImpactLog(data.log || []);
    } catch (err: any) {
      toast.error("Failed to load impact log");
      setImpactLog([]);
    }
    setLoadingLog(false);
  };

  const handleUpdatePoints = async () => {
    if (!selectedUser || pointsAdjustment === 0) return;
    
    try {
      const { data } = await adminService.updateUserPoints(
        selectedUser.id,
        pointsAdjustment,
        adjustmentReason || "Manual admin adjustment"
      );
      
      // Update user in the list
      setUsers(users.map(u => 
        u.id === selectedUser.id 
          ? { ...u, impact_score: data.new_score }
          : u
      ));
      
      // Update selected user
      setSelectedUser({ ...selectedUser, impact_score: data.new_score });
      
      toast.success(data.message);
      
      // Reload impact log
      const logRes = await adminService.getUserImpactLog(selectedUser.id);
      setImpactLog(logRes.data.log || []);
      
      // Reset form
      setPointsAdjustment(0);
      setAdjustmentReason("");
      
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to update points");
    }
  };

  const visibleGroups = groups.filter((group) => {
    const query = search.trim().toLowerCase();
    return !query || group.name.toLowerCase().includes(query) || group.slug.toLowerCase().includes(query);
  });

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">User Management</h1>
        <p className="text-slate-600 mt-1">Manage all platform users</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-200 pb-4">
          {([
            ["users", "Users", User],
            ["hubs", "Citizen Hubs", Building2],
            ["official", "Official Hubs", Shield],
            ["communities", "Communities", Globe2],
            ["authorities", "Authorities", Shield],
          ] as const).map(([tab, label, Icon]) => (
            <button
              key={tab}
              onClick={() => selectTab(tab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
                activeTab === tab
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder={
                activeTab === "hubs" || activeTab === "official" || activeTab === "communities"
                  ? "Search groups..."
                  : "Search by name, username, or email..."
              }
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (activeTab === "hubs" || activeTab === "official" || activeTab === "communities") && visibleGroups.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-500">No {activeTab === "communities" ? "communities" : "citizen hubs"} found</p>
          </div>
        ) : activeTab === "hubs" || activeTab === "official" || activeTab === "communities" ? (
          <>
            <div className="flex items-center justify-between mb-3">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={visibleGroups.length > 0 && visibleGroups.every((group) => selectedGroups.has(group.id))}
                  onChange={() => {
                    if (visibleGroups.every((group) => selectedGroups.has(group.id))) {
                      setSelectedGroups(new Set());
                    } else {
                      setSelectedGroups(new Set(visibleGroups.map((group) => group.id)));
                    }
                  }}
                />
                Select all
              </label>
              <button
                onClick={handleDeleteSelectedGroups}
                disabled={selectedGroups.size === 0}
                className="inline-flex items-center gap-2 px-3 py-2 text-sm text-white bg-red-600 rounded-lg disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" />
                Delete selected ({selectedGroups.size})
              </button>
            </div>
            <div className="divide-y divide-slate-100">
            {visibleGroups.map((group) => (
              <div key={group.id} className="flex items-center justify-between gap-4 py-4">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedGroups.has(group.id)}
                    onChange={() => toggleSelected(group.id, setSelectedGroups)}
                  />
                  <div>
                  <p className="font-medium text-slate-900">{group.name}</p>
                  <p className="text-sm text-slate-500">@{group.slug}</p>
                  {group.description && <p className="text-sm text-slate-600 mt-1">{group.description}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-slate-500">
                    {group.member_count || 0} members · {group.total_points || 0} points
                  </span>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    group.is_active === false
                      ? "bg-red-100 text-red-700"
                      : "bg-green-100 text-green-700"
                  }`}>
                    {group.is_active === false ? "Inactive" : "Active"}
                  </span>
                  <button
                    onClick={() => handleToggleGroupActive(group)}
                    className={group.is_active === false ? "text-green-600 hover:text-green-700" : "text-amber-600 hover:text-amber-700"}
                    title={group.is_active === false ? "Activate group" : "Deactivate group"}
                  >
                    {group.is_active === false ? <CheckCircle className="h-5 w-5" /> : <Ban className="h-5 w-5" />}
                  </button>
                  <button
                    onClick={() => handleDeleteGroup(group)}
                    className="text-red-600 hover:text-red-700"
                    title="Delete group"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>
              </div>
            ))}
            </div>
          </>
        ) : users.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-500">No {activeTab === "authorities" ? "authorities" : "users"} found</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-slate-600">
                {selectedUsers.size} selected
              </span>
              <button
                onClick={handleDeleteSelectedUsers}
                disabled={selectedUsers.size === 0}
                className="inline-flex items-center gap-2 px-3 py-2 text-sm text-white bg-red-600 rounded-lg disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" />
                Delete selected
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="py-3 px-4">
                      <input
                        type="checkbox"
                        checked={users.length > 0 && users.every((user) => selectedUsers.has(user.id))}
                        onChange={() => {
                          if (users.every((user) => selectedUsers.has(user.id))) {
                            setSelectedUsers(new Set());
                          } else {
                            setSelectedUsers(new Set(users.map((user) => user.id)));
                          }
                        }}
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">User</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">Category</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">Stats</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">Role</th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-slate-700">Status</th>
                    <th className="text-right py-3 px-4 text-sm font-semibold text-slate-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          checked={selectedUsers.has(user.id)}
                          onChange={() => toggleSelected(user.id, setSelectedUsers)}
                          disabled={user.role === "admin"}
                        />
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={user.avatar.url || "/default-avatar.png"}
                            alt={user.name}
                            className="w-10 h-10 rounded-full object-cover"
                          />
                          <div>
                            <p className="font-medium text-slate-900">{user.name}</p>
                            <p className="text-sm text-slate-600">{user.email}</p>
                            <p className="text-xs text-slate-400">@{user.username}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-slate-600">{user.category}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm text-slate-600">
                          <div>{user.posts_count} posts</div>
                          <div>{user.followers_count} followers</div>
                          <div>{user.impact_score} points</div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => handleToggleRole(user.id, user.role)}
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                            user.role === "admin"
                              ? "bg-purple-100 text-purple-700"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {user.role === "admin" ? <Shield className="h-3 w-3" /> : <User className="h-3 w-3" />}
                          {user.role}
                        </button>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                            user.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => openPointsModal(user)}
                            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                            title="Manage Points"
                          >
                            <TrendingUp className="h-4 w-4 text-orange-600" />
                          </button>
                          <button
                            onClick={() => handleToggleActive(user.id)}
                            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                            title={user.is_active ? "Deactivate" : "Activate"}
                          >
                            {user.is_active ? (
                              <Ban className="h-4 w-4 text-red-600" />
                            ) : (
                              <CheckCircle className="h-4 w-4 text-green-600" />
                            )}
                          </button>
                          <button
                            onClick={() => handleResetPassword(user.id, user.username)}
                            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                            title="Change Password"
                          >
                            <Key className="h-4 w-4 text-blue-600" />
                          </button>
                          {user.role !== "admin" && (
                            <button
                              onClick={() => handleDelete(user.id, user.username)}
                              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-600">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-slate-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Points Management Modal */}
      {showPointsModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-100">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">Manage Points</h2>
                  <p className="text-slate-600 mt-1">
                    @{selectedUser.username} • Current: <span className="font-bold text-orange-600">{selectedUser.impact_score}</span> points
                  </p>
                </div>
                <button
                  onClick={() => setShowPointsModal(false)}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  <X className="h-5 w-5 text-slate-500" />
                </button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Points Adjustment Form */}
              <div className="bg-slate-50 rounded-xl p-4 space-y-4">
                <h3 className="font-semibold text-slate-900">Adjust Points</h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Points Change
                    </label>
                    <input
                      type="number"
                      value={pointsAdjustment}
                      onChange={(e) => setPointsAdjustment(Number(e.target.value))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                      placeholder="e.g., 100 or -50"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Use positive numbers to add, negative to subtract
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Reason
                    </label>
                    <input
                      type="text"
                      value={adjustmentReason}
                      onChange={(e) => setAdjustmentReason(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                      placeholder="Testing purposes, etc."
                    />
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleUpdatePoints}
                    disabled={pointsAdjustment === 0}
                    className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <TrendingUp className="h-4 w-4" />
                    {pointsAdjustment > 0 ? 'Add Points' : pointsAdjustment < 0 ? 'Deduct Points' : 'Update Points'}
                  </button>
                  
                  {pointsAdjustment !== 0 && (
                    <div className="flex items-center text-sm text-slate-600">
                      New Total: <span className="font-bold ml-1 text-orange-600">
                        {selectedUser.impact_score + pointsAdjustment}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Impact History */}
              <div>
                <h3 className="font-semibold text-slate-900 mb-3">Impact History</h3>
                
                {loadingLog ? (
                  <div className="text-center py-8 text-slate-500">Loading...</div>
                ) : impactLog.length === 0 ? (
                  <div className="text-center py-8 text-slate-500">No impact history yet</div>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {impactLog.map((log, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg text-sm">
                        <div>
                          <p className="font-medium text-slate-900">{log.action}</p>
                          <p className="text-xs text-slate-500">
                            {new Date(log.created_at).toLocaleDateString()} {new Date(log.created_at).toLocaleTimeString()}
                          </p>
                        </div>
                        <span className={`font-bold ${
                          log.points > 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {log.points > 0 ? '+' : ''}{log.points}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
