import { useEffect, useState } from "react";
import {
  Card, Table, Button, Tag, Space, Modal, Form, Input, Select, App as AntApp, Popconfirm,
} from "antd";
import { PlusOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { api, get } from "../api";
import { useAuth } from "../auth";

interface UserRow {
  username: string;
  role: "admin" | "user";
  allowed_projects: string[];
  created_at?: string;
}

export default function Admin() {
  const { user: currentUser } = useAuth();
  const { message } = AntApp.useApp();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const [u, p] = await Promise.all([
        get<UserRow[]>("/admin/users"),
        get<{ project_id: string }[]>("/admin/projects"),
      ]);
      setUsers(u);
      setProjects(p.map((r) => r.project_id));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ role: "user", allowed_projects: [] });
    setModalOpen(true);
  };

  const openEdit = (u: UserRow) => {
    setEditing(u);
    form.resetFields();
    form.setFieldsValue({
      username: u.username,
      role: u.role,
      allowed_projects: u.allowed_projects || [],
      password: "",
    });
    setModalOpen(true);
  };

  const submit = async () => {
    try {
      const v = await form.validateFields();
      if (editing) {
        const body: any = { role: v.role, allowed_projects: v.allowed_projects || [] };
        if (v.password) body.password = v.password;
        await api.patch(`/admin/users/${editing.username}`, body);
        message.success(`Updated ${editing.username}`);
      } else {
        await api.post("/admin/users", {
          username: v.username,
          password: v.password,
          role: v.role,
          allowed_projects: v.allowed_projects || [],
        });
        message.success(`Created ${v.username}`);
      }
      setModalOpen(false);
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (username: string) => {
    try {
      await api.delete(`/admin/users/${username}`);
      message.success(`Deleted ${username}`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const columns = [
    { title: "User", dataIndex: "username", key: "username" },
    {
      title: "Role", dataIndex: "role", key: "role",
      render: (r: string) => <Tag color={r === "admin" ? "gold" : "blue"}>{r}</Tag>,
    },
    {
      title: "Allowed projects",
      dataIndex: "allowed_projects",
      key: "allowed_projects",
      render: (a: string[], row: UserRow) =>
        row.role === "admin"
          ? <Tag color="green">all projects</Tag>
          : (a && a.length ? a.map((p) => <Tag key={p}>{p}</Tag>) : <Tag color="red">none</Tag>),
    },
    { title: "Created", dataIndex: "created_at", key: "created_at",
      render: (v: string) => v ? new Date(v).toLocaleString() : "—" },
    {
      title: "Actions", key: "actions",
      render: (_: any, row: UserRow) => (
        <Space>
          <Button data-testid={`edit-user-${row.username}`} icon={<EditOutlined />} onClick={() => openEdit(row)}>Edit</Button>
          <Popconfirm
            title={`Delete ${row.username}?`}
            onConfirm={() => remove(row.username)}
            okText="Delete"
            okButtonProps={{ danger: true }}
            disabled={row.username === currentUser}
          >
            <Button data-testid={`delete-user-${row.username}`} danger icon={<DeleteOutlined />} disabled={row.username === currentUser}>
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="admin-view">
      <Card
        title="Users & access (RBAC)"
        extra={
          <Button data-testid="create-user-btn" type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            New user
          </Button>
        }
      >
        <Table
          rowKey="username"
          loading={loading}
          dataSource={users}
          columns={columns as any}
          pagination={false}
          data-testid="users-table"
        />
      </Card>

      <Modal
        open={modalOpen}
        title={editing ? `Edit ${editing.username}` : "Create user"}
        onCancel={() => setModalOpen(false)}
        onOk={submit}
        okText="Save"
        destroyOnClose
        data-testid="user-form-modal"
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <Form.Item name="username" label="Username" rules={[{ required: true, message: "Required" }]}>
              <Input data-testid="user-form-username" autoFocus />
            </Form.Item>
          )}
          <Form.Item
            name="password"
            label={editing ? "New password (leave blank to keep)" : "Password"}
            rules={editing ? [] : [{ required: true, message: "Required" }]}
          >
            <Input.Password data-testid="user-form-password" />
          </Form.Item>
          <Form.Item name="role" label="Role" rules={[{ required: true }]}>
            <Select
              data-testid="user-form-role"
              options={[
                { value: "user", label: "User (project-scoped)" },
                { value: "admin", label: "Admin (full access)" },
              ]}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, cur) => prev.role !== cur.role}
          >
            {({ getFieldValue }) =>
              getFieldValue("role") === "user" ? (
                <Form.Item
                  name="allowed_projects"
                  label="Allowed projects"
                  tooltip="Pick which projects this user can see. Empty = no access."
                >
                  <Select
                    data-testid="user-form-projects"
                    mode="multiple"
                    placeholder="Select projects"
                    options={projects.map((p) => ({ value: p, label: p }))}
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
