import { AnimatePresence, MotionConfig } from "framer-motion";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import Layout from "./components/Layout";
import { PageTransition, Toaster } from "./components/motion";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import { useAuth } from "./store/auth";

// Admin pages lazy: student ke phone pe admin code (charts etc.) download hi nahi hota.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Profile = lazy(() => import("./pages/Profile"));
const AdminOverview = lazy(() => import("./pages/admin/Overview"));
const Students = lazy(() => import("./pages/admin/Students"));
const StudentDetail = lazy(() => import("./pages/admin/StudentDetail"));
const Attendance = lazy(() => import("./pages/admin/Attendance"));
const Live = lazy(() => import("./pages/admin/Live"));
const Reports = lazy(() => import("./pages/admin/Reports"));
const Batches = lazy(() => import("./pages/admin/Batches"));
const Teachers = lazy(() => import("./pages/admin/Teachers"));
const Holidays = lazy(() => import("./pages/admin/Holidays"));
const Leaves = lazy(() => import("./pages/admin/Leaves"));

export const homeFor = (role) => (role === "student" ? "/dashboard" : "/admin");
const STAFF = ["admin", "teacher"];

function Guard({ role, children }) {
  const { token, user } = useAuth();
  if (!token || !user) return <Navigate to="/login" replace />;
  const allowed = !role || (Array.isArray(role) ? role.includes(user.role) : user.role === role);
  if (!allowed) return <Navigate to={homeFor(user.role)} replace />;
  return (
    <Layout>
      <Suspense fallback={<Spinner />}>
        <PageTransition>{children}</PageTransition>
      </Suspense>
    </Layout>
  );
}

function Home() {
  const user = useAuth((s) => s.user);
  return <Navigate to={!user ? "/login" : homeFor(user.role)} replace />;
}

const PAGES = [
  ["/dashboard", "student", Dashboard],
  ["/profile", null, Profile],
  // teacher = staff, but server-side scoped to assigned batches
  ["/admin", STAFF, AdminOverview],
  ["/admin/students", STAFF, Students],
  ["/admin/students/:id", STAFF, StudentDetail],
  ["/admin/attendance", STAFF, Attendance],
  ["/admin/live", STAFF, Live],
  ["/admin/reports", STAFF, Reports],
  ["/admin/leaves", STAFF, Leaves],
  ["/admin/batches", "admin", Batches],
  ["/admin/teachers", "admin", Teachers],
  ["/admin/holidays", "admin", Holidays],
];

export default function App() {
  const location = useLocation();
  return (
    <MotionConfig reducedMotion="user">
      <Toaster />
      <AnimatePresence mode="wait" initial={false}>
        <Routes location={location} key={location.pathname.startsWith("/admin") || location.pathname === "/dashboard" || location.pathname === "/profile" ? "app" : location.pathname}>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<PageTransition><Login /></PageTransition>} />
          <Route path="/signup" element={<PageTransition><Signup /></PageTransition>} />
          {PAGES.map(([path, role, Page]) => (
            <Route key={path} path={path} element={<Guard role={role}><Page /></Guard>} />
          ))}
          <Route path="*" element={<Home />} />
        </Routes>
      </AnimatePresence>
    </MotionConfig>
  );
}
