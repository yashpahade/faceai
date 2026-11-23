import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App";
import AttendanceTable from "./components/AttendanceTable";
import { useAuth } from "./store/auth";

const renderAt = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );

describe("routing guards", () => {
  beforeEach(() => useAuth.getState().logout());

  it("redirects anonymous users to login", async () => {
    renderAt("/admin/students");
    expect(await screen.findByRole("tab", { name: "Face login" })).toBeInTheDocument();
  });

  it("keeps students out of admin pages", async () => {
    useAuth.getState().setSession("t", { role: "student", full_name: "Asha Rao", face_enrolled: true });
    renderAt("/admin");
    expect(await screen.findByRole("heading", { name: /Asha/ })).toBeInTheDocument();
  });
});

describe("teacher role", () => {
  beforeEach(() => useAuth.getState().logout());
  it("can open staff pages but not admin-only pages", async () => {
    useAuth.getState().setSession("t", { role: "teacher", full_name: "Teacher One" });
    renderAt("/admin/teachers"); // admin-only -> redirected to overview
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.queryAllByRole("link", { name: /Teachers/ })).toHaveLength(0);
    expect(screen.getAllByRole("link", { name: /Leaves/ }).length).toBeGreaterThan(0);
  });
});

describe("AttendanceTable", () => {
  const rows = [
    { user_id: "1", full_name: "Asha", batch: "B1", day: "2026-11-20", status: "present", method: "face", confidence: 0.81 },
    { user_id: "2", full_name: "Ravi", batch: "B1", day: "2026-11-20", status: "absent", method: null, confidence: null },
  ];
  it("filters by search text", async () => {
    const { getByLabelText, findAllByText } = render(<AttendanceTable rows={rows} />);
    getByLabelText("Search").value = "";
    expect(await findAllByText("2 records")).toHaveLength(1);
  });
});
