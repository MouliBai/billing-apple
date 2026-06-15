import { useState, useEffect, useRef } from "react";

// ─────────────────────────────────────────────────────────────
//  DESIGN TOKENS — centralized gradient palette
//  All colors live here; components import via JS object
// ─────────────────────────────────────────────────────────────
const TOKENS = {
  grad1: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
  grad2: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
  gradAccent: "linear-gradient(90deg, #e94560 0%, #f5a623 100%)",
  gradCard: "linear-gradient(145deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)",
  gradBtn: "linear-gradient(90deg, #e94560 0%, #c0392b 100%)",
  gradBtnSecondary: "linear-gradient(90deg, #2980b9 0%, #1a5276 100%)",
  gradSuccess: "linear-gradient(90deg, #27ae60, #1e8449)",
  glass: "rgba(255,255,255,0.06)",
  glassBorder: "rgba(255,255,255,0.12)",
  textPrimary: "#f0f4f8",
  textSecondary: "rgba(240,244,248,0.65)",
  textMuted: "rgba(240,244,248,0.35)",
  accent: "#e94560",
  accentGlow: "0 0 24px rgba(233,69,96,0.35)",
  inputBg: "rgba(255,255,255,0.05)",
  inputBorder: "rgba(255,255,255,0.15)",
  inputFocusBorder: "#e94560",
  transitionFast: "all 0.18s cubic-bezier(.4,0,.2,1)",
  transitionMed: "all 0.35s cubic-bezier(.4,0,.2,1)",
  radiusLg: "16px",
  radiusMd: "10px",
  radiusSm: "6px",
};

// ─────────────────────────────────────────────────────────────
//  KEYFRAME ANIMATIONS — injected once as a style tag
// ─────────────────────────────────────────────────────────────
function GlobalStyles() {
  // Injects animation keyframes needed by all views
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'Sora', sans-serif; }
      @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes fadeSlideLeft {
        from { opacity: 0; transform: translateX(-24px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      @keyframes fadeSlideRight {
        from { opacity: 0; transform: translateX(24px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      @keyframes pulseGlow {
        0%,100% { box-shadow: 0 0 20px rgba(233,69,96,0.2); }
        50%      { box-shadow: 0 0 40px rgba(233,69,96,0.5); }
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
      @keyframes shimmer {
        0%   { background-position: -400px 0; }
        100% { background-position: 400px 0; }
      }
      @keyframes floatY {
        0%,100% { transform: translateY(0px); }
        50%      { transform: translateY(-12px); }
      }
      @keyframes expandWidth {
        from { width: 0%; }
        to   { width: 100%; }
      }
      .anim-fade   { animation: fadeSlideIn 0.45s ease both; }
      .anim-left   { animation: fadeSlideLeft 0.45s ease both; }
      .anim-right  { animation: fadeSlideRight 0.45s ease both; }
      input:-webkit-autofill {
        -webkit-box-shadow: 0 0 0 100px #1a1a2e inset !important;
        -webkit-text-fill-color: #f0f4f8 !important;
      }
    `}</style>
  );
}

// ─────────────────────────────────────────────────────────────
//  REUSABLE: StyledInput — dark glass text field with label
// ─────────────────────────────────────────────────────────────
function StyledInput({ label, icon, type = "text", value, onChange, placeholder, disabled }) {
  // Manages focus highlight ring and label float animation
  const [focused, setFocused] = useState(false);
  const styles = {
    wrapper: { display: "flex", flexDirection: "column", gap: 6, width: "100%" },
    label: {
      fontSize: 12,
      fontWeight: 500,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: focused ? TOKENS.accent : TOKENS.textSecondary,
      transition: TOKENS.transitionFast,
    },
    inputRow: {
      display: "flex",
      alignItems: "center",
      background: TOKENS.inputBg,
      border: `1.5px solid ${focused ? TOKENS.inputFocusBorder : TOKENS.inputBorder}`,
      borderRadius: TOKENS.radiusMd,
      transition: TOKENS.transitionFast,
      overflow: "hidden",
      boxShadow: focused ? `0 0 0 3px rgba(233,69,96,0.12)` : "none",
    },
    iconSpan: {
      padding: "0 12px",
      fontSize: 16,
      color: focused ? TOKENS.accent : TOKENS.textMuted,
      transition: TOKENS.transitionFast,
    },
    input: {
      flex: 1,
      background: "transparent",
      border: "none",
      outline: "none",
      padding: "12px 14px 12px 0",
      fontSize: 14,
      color: TOKENS.textPrimary,
      fontFamily: "'Sora', sans-serif",
      width: "100%",
    },
  };
  return (
    <div style={styles.wrapper}>
      {label && <label style={styles.label}>{label}</label>}
      <div style={styles.inputRow}>
        {icon && <span style={styles.iconSpan}>{icon}</span>}
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          style={styles.input}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  REUSABLE: GradientButton — animated CTA button
// ─────────────────────────────────────────────────────────────
function GradientButton({ children, onClick, variant = "primary", loading, fullWidth, small }) {
  // Handles hover lift + loading spinner state
  const [hovered, setHovered] = useState(false);
  const grad = variant === "primary" ? TOKENS.gradBtn
    : variant === "success" ? TOKENS.gradSuccess
    : TOKENS.gradBtnSecondary;
  const styles = {
    button: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      background: grad,
      border: "none",
      borderRadius: TOKENS.radiusMd,
      padding: small ? "8px 18px" : "13px 28px",
      fontSize: small ? 13 : 15,
      fontWeight: 600,
      fontFamily: "'Sora', sans-serif",
      color: "#fff",
      cursor: loading ? "not-allowed" : "pointer",
      width: fullWidth ? "100%" : "auto",
      transition: TOKENS.transitionFast,
      transform: hovered && !loading ? "translateY(-2px)" : "translateY(0)",
      boxShadow: hovered && !loading
        ? "0 8px 24px rgba(233,69,96,0.4)"
        : "0 4px 12px rgba(0,0,0,0.3)",
      opacity: loading ? 0.75 : 1,
      letterSpacing: "0.02em",
    },
    spinner: {
      width: 16, height: 16,
      border: "2px solid rgba(255,255,255,0.3)",
      borderTopColor: "#fff",
      borderRadius: "50%",
      animation: "spin 0.6s linear infinite",
    },
  };
  return (
    <button
      style={styles.button}
      onClick={!loading ? onClick : undefined}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {loading && <span style={styles.spinner} />}
      {children}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
//  REUSABLE: Toast notification
// ─────────────────────────────────────────────────────────────
function Toast({ message, type, onClose }) {
  // Auto-dismiss and slide-in toast for feedback messages
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, []);
  const colors = {
    success: { bg: "rgba(39,174,96,0.15)", border: "rgba(39,174,96,0.4)", icon: "✓" },
    error:   { bg: "rgba(233,69,96,0.15)",  border: "rgba(233,69,96,0.4)",  icon: "✕" },
    info:    { bg: "rgba(41,128,185,0.15)", border: "rgba(41,128,185,0.4)", icon: "ℹ" },
  }[type] || {};
  return (
    <div style={{
      position: "fixed", top: 24, right: 24, zIndex: 9999,
      background: colors.bg, border: `1px solid ${colors.border}`,
      borderRadius: TOKENS.radiusMd, padding: "14px 20px",
      display: "flex", alignItems: "center", gap: 10,
      backdropFilter: "blur(12px)",
      animation: "fadeSlideLeft 0.3s ease both",
      maxWidth: 340,
    }}>
      <span style={{ fontSize: 18, fontWeight: 700 }}>{colors.icon}</span>
      <span style={{ fontSize: 14, color: TOKENS.textPrimary }}>{message}</span>
      <button onClick={onClose} style={{
        background: "none", border: "none", color: TOKENS.textMuted,
        cursor: "pointer", fontSize: 16, marginLeft: "auto",
      }}>×</button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  RIGHT PANEL — company branding shown on split layout pages
// ─────────────────────────────────────────────────────────────
function CompanyPanel() {
  // Static right-side company info panel with floating animation
  const features = [
    { icon: "🔐", title: "Bank-grade Security", desc: "End-to-end encrypted 2FA with TOTP authentication" },
    { icon: "⚡", title: "Lightning Fast", desc: "Sub-second response for all business operations" },
    { icon: "📊", title: "Smart Dashboard", desc: "Real-time insights and business intelligence tools" },
    { icon: "🏢", title: "Multi-tenant", desc: "Manage multiple companies from a single platform" },
  ];
  return (
    <div style={{
      flex: 1,
      background: TOKENS.grad1,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      padding: "60px 48px",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Decorative background orbs */}
      <div style={{
        position: "absolute", top: -80, right: -80,
        width: 320, height: 320,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(233,69,96,0.15) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", bottom: -60, left: -60,
        width: 260, height: 260,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(41,128,185,0.15) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      {/* Logo / brand mark */}
      <div className="anim-right" style={{ marginBottom: 40 }}>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 20px",
          background: TOKENS.glass,
          border: `1px solid ${TOKENS.glassBorder}`,
          borderRadius: 50,
          marginBottom: 32,
        }}>
          <span style={{ fontSize: 22 }}>⚡</span>
          <span style={{
            fontSize: 15, fontWeight: 700,
            letterSpacing: "0.12em",
            background: TOKENS.gradAccent,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>EVO AURA</span>
        </div>

        <h1 style={{
          fontSize: 38, fontWeight: 700, lineHeight: 1.2,
          color: TOKENS.textPrimary, marginBottom: 16,
        }}>
          The future of<br />
          <span style={{
            background: TOKENS.gradAccent,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>business management</span>
        </h1>
        <p style={{
          fontSize: 15, color: TOKENS.textSecondary,
          lineHeight: 1.7, maxWidth: 380,
        }}>
          EvoAura brings together secure authentication, real-time analytics,
          and powerful company tooling — all in one elegant platform built for
          modern teams.
        </p>
      </div>

      {/* Feature list */}
      <div className="anim-right" style={{
        display: "flex", flexDirection: "column", gap: 16,
        animationDelay: "0.1s",
      }}>
        {features.map((f, i) => (
          <div key={i} style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 14,
            padding: "14px 18px",
            background: TOKENS.gradCard,
            border: `1px solid ${TOKENS.glassBorder}`,
            borderRadius: TOKENS.radiusMd,
            backdropFilter: "blur(8px)",
          }}>
            <span style={{ fontSize: 22, flexShrink: 0, marginTop: 1 }}>{f.icon}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: TOKENS.textPrimary, marginBottom: 3 }}>
                {f.title}
              </div>
              <div style={{ fontSize: 12, color: TOKENS.textSecondary, lineHeight: 1.5 }}>
                {f.desc}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer links */}
      <div className="anim-right" style={{
        marginTop: 36, display: "flex", gap: 20,
        animationDelay: "0.2s",
      }}>
        {["Privacy Policy", "Terms of Service", "Support"].map(link => (
          <a key={link} href="#" style={{
            fontSize: 12,
            color: TOKENS.textMuted,
            textDecoration: "none",
            transition: TOKENS.transitionFast,
            borderBottom: "1px solid transparent",
          }}
          onMouseEnter={e => {
            e.target.style.color = TOKENS.accent;
            e.target.style.borderBottomColor = TOKENS.accent;
          }}
          onMouseLeave={e => {
            e.target.style.color = TOKENS.textMuted;
            e.target.style.borderBottomColor = "transparent";
          }}>
            {link}
          </a>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: AskDBName — first-time company name setup
// ─────────────────────────────────────────────────────────────
function AskDBNameView({ onNext }) {
  // Collects company name and validates before advancing to auth step
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  const handleNext = () => {
    // Sanitize and append .db extension
    const clean = name.trim().replace(/\s+/g, "_");
    if (!clean) return;
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onNext(clean.endsWith(".db") ? clean : `${clean}.db`);
    }, 600);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 56px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-left" style={{ width: "100%", maxWidth: 400 }}>
        {/* Step indicator */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, marginBottom: 36,
        }}>
          {[1,2,3].map(n => (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: "50%",
                background: n === 1 ? TOKENS.gradBtn : TOKENS.glass,
                border: `1.5px solid ${n === 1 ? TOKENS.accent : TOKENS.glassBorder}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 700, color: "#fff",
              }}>{n}</div>
              {n < 3 && <div style={{
                width: 32, height: 1.5,
                background: TOKENS.glassBorder,
              }} />}
            </div>
          ))}
          <span style={{ fontSize: 12, color: TOKENS.textMuted, marginLeft: 8 }}>
            Step 1 of 3
          </span>
        </div>

        <h2 style={{
          fontSize: 28, fontWeight: 700, color: TOKENS.textPrimary,
          marginBottom: 8,
        }}>Set up your workspace</h2>
        <p style={{
          fontSize: 14, color: TOKENS.textSecondary, marginBottom: 36, lineHeight: 1.6,
        }}>
          Enter your company name to create a secure database.
          This becomes your workspace identifier.
        </p>

        <StyledInput
          label="Company Name"
          icon="🏢"
          value={name}
          onChange={setName}
          placeholder="e.g. TechCorp, My Shop, Acme"
        />

        <div style={{ marginTop: 10, marginBottom: 32 }}>
          {name && (
            <p style={{ fontSize: 12, color: TOKENS.textMuted }}>
              Database file:{" "}
              <span style={{
                color: TOKENS.accent,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {name.trim().replace(/\s+/g, "_")}.db
              </span>
            </p>
          )}
        </div>

        <GradientButton onClick={handleNext} loading={loading} fullWidth>
          Continue →
        </GradientButton>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: StartupAuth — master TOTP verification for new DB
// ─────────────────────────────────────────────────────────────
function StartupAuthView({ dbName, onSuccess, showToast }) {
  // Verifies the master setup code before database creation
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);

  const handleVerify = () => {
    // Simulate TOTP verification — replace with real API call
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      if (code.length === 6) {
        showToast("Database created successfully!", "success");
        onSuccess();
      } else {
        showToast("Invalid master code. Please try again.", "error");
      }
    }, 700);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 56px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-left" style={{ width: "100%", maxWidth: 400 }}>
        <div style={{ marginBottom: 36 }}>
          {/* Lock icon badge */}
          <div style={{
            width: 56, height: 56,
            borderRadius: "50%",
            background: "rgba(233,69,96,0.12)",
            border: "2px solid rgba(233,69,96,0.3)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 26, marginBottom: 24,
            animation: "pulseGlow 2.5s ease infinite",
          }}>🔐</div>
          <h2 style={{
            fontSize: 26, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 8,
          }}>Security Verification</h2>
          <p style={{ fontSize: 14, color: TOKENS.textSecondary, lineHeight: 1.6 }}>
            Enter your 6-digit master TOTP code to authorize creation of{" "}
            <span style={{
              color: TOKENS.accent,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
            }}>{dbName}</span>
          </p>
        </div>

        <StyledInput
          label="Master Setup Code"
          icon="🔑"
          type="password"
          value={code}
          onChange={setCode}
          placeholder="6-digit TOTP code"
        />

        <div style={{ marginTop: 28 }}>
          <GradientButton onClick={handleVerify} loading={loading} fullWidth>
            Verify & Create Database
          </GradientButton>
        </div>

        <p style={{
          fontSize: 12, color: TOKENS.textMuted,
          textAlign: "center", marginTop: 20, lineHeight: 1.6,
        }}>
          This code comes from your authenticator app linked to<br />
          the master secret key.
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: SignupForm — new user creation with 2FA setup
// ─────────────────────────────────────────────────────────────
function SignupView({ dbName, onSuccess, onSwitchToLogin, showToast }) {
  // Creates a new user with username/password + master code verification
  const [form, setForm] = useState({
    username: "", password: "", confirm: "", master: "",
  });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const set = k => v => setForm(prev => ({ ...prev, [k]: v }));

  const handleCreate = () => {
    // Validate all fields before creating user
    const { username, password, confirm, master } = form;
    if (!username || !password || !confirm || !master) {
      showToast("Please fill in all fields.", "error"); return;
    }
    if (password !== confirm) {
      showToast("Passwords do not match.", "error"); return;
    }
    if (master.length !== 6) {
      showToast("Master code must be 6 digits.", "error"); return;
    }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      showToast("Account created! Set up your 2FA now.", "success");
      onSuccess({ username, password });
    }, 900);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 56px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-left" style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ marginBottom: 32 }}>
          <h2 style={{
            fontSize: 28, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 8,
          }}>Create Account</h2>
          <p style={{ fontSize: 14, color: TOKENS.textSecondary }}>
            {dbName && (
              <>Joining workspace{" "}
                <span style={{ color: TOKENS.accent, fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
                  {dbName}
                </span>
              </>
            )}
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <StyledInput label="Username" icon="👤"
            value={form.username} onChange={set("username")} placeholder="Choose a username" />
          <StyledInput label="Password" icon="🔒"
            type={showPass ? "text" : "password"}
            value={form.password} onChange={set("password")} placeholder="Create a strong password" />
          <StyledInput label="Confirm Password" icon="🔒"
            type={showPass ? "text" : "password"}
            value={form.confirm} onChange={set("confirm")} placeholder="Repeat your password" />

          {/* Password strength bar */}
          {form.password && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: TOKENS.textMuted }}>Password strength</span>
                <span style={{
                  fontSize: 11,
                  color: form.password.length > 10 ? "#27ae60"
                    : form.password.length > 6 ? "#f5a623" : "#e94560",
                }}>
                  {form.password.length > 10 ? "Strong" : form.password.length > 6 ? "Medium" : "Weak"}
                </span>
              </div>
              <div style={{
                height: 4, borderRadius: 2,
                background: "rgba(255,255,255,0.08)",
                overflow: "hidden",
              }}>
                <div style={{
                  height: "100%",
                  width: `${Math.min(100, form.password.length * 9)}%`,
                  background: form.password.length > 10 ? "#27ae60"
                    : form.password.length > 6 ? "#f5a623" : "#e94560",
                  transition: TOKENS.transitionMed,
                  borderRadius: 2,
                }} />
              </div>
            </div>
          )}

          {/* Show password toggle */}
          <label style={{
            display: "flex", alignItems: "center", gap: 8,
            cursor: "pointer", fontSize: 13, color: TOKENS.textSecondary,
          }}>
            <input
              type="checkbox"
              checked={showPass}
              onChange={e => setShowPass(e.target.checked)}
              style={{ accentColor: TOKENS.accent }}
            />
            Show passwords
          </label>

          <div style={{
            height: 1,
            background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)",
          }} />

          <StyledInput label="Master Setup Code" icon="🛡️"
            type="password"
            value={form.master} onChange={set("master")} placeholder="6-digit TOTP code" />
        </div>

        <div style={{ marginTop: 28 }}>
          <GradientButton onClick={handleCreate} loading={loading} fullWidth>
            Create Account
          </GradientButton>
        </div>

        <p style={{
          textAlign: "center", marginTop: 24,
          fontSize: 13, color: TOKENS.textSecondary,
        }}>
          Already have an account?{" "}
          <a onClick={onSwitchToLogin} style={{
            color: TOKENS.accent, cursor: "pointer",
            textDecoration: "none", fontWeight: 600,
          }}>Sign in →</a>
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: LoginForm — credential + 2FA login with user dropdown
// ─────────────────────────────────────────────────────────────
function LoginView({ dbName, users, onSuccess, onSwitchToSignup, showToast }) {
  // Handles username selection, password entry, and OTP verification
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = () => {
    // Validate fields then attempt authentication
    if (!username || !password) {
      showToast("Please enter username and password.", "error"); return;
    }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      showToast("Login successful! Welcome back.", "success");
      onSuccess({ username });
    }, 800);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 56px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-left" style={{ width: "100%", maxWidth: 400 }}>
        <div style={{ marginBottom: 36 }}>
          <div style={{
            display: "inline-block",
            padding: "6px 16px",
            background: "rgba(233,69,96,0.1)",
            border: "1px solid rgba(233,69,96,0.25)",
            borderRadius: 50,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.1em",
            color: TOKENS.accent,
            textTransform: "uppercase",
            marginBottom: 20,
          }}>
            Welcome Back
          </div>
          <h2 style={{
            fontSize: 30, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 8,
          }}>Sign In</h2>
          {dbName && (
            <p style={{ fontSize: 14, color: TOKENS.textSecondary }}>
              Workspace:{" "}
              <span style={{
                color: TOKENS.accent,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
              }}>{dbName}</span>
            </p>
          )}
        </div>

        {/* Username as stylish select or input */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {users && users.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{
                fontSize: 12, fontWeight: 500, letterSpacing: "0.08em",
                textTransform: "uppercase", color: TOKENS.textSecondary,
              }}>Username</label>
              <div style={{
                background: TOKENS.inputBg,
                border: `1.5px solid ${TOKENS.inputBorder}`,
                borderRadius: TOKENS.radiusMd,
                overflow: "hidden",
              }}>
                <select
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  style={{
                    width: "100%",
                    background: "transparent",
                    border: "none",
                    outline: "none",
                    padding: "12px 16px",
                    fontSize: 14,
                    color: TOKENS.textPrimary,
                    fontFamily: "'Sora', sans-serif",
                    cursor: "pointer",
                  }}
                >
                  <option value="" style={{ background: "#1a1a2e" }}>Select username</option>
                  {users.map(u => (
                    <option key={u} value={u} style={{ background: "#1a1a2e" }}>{u}</option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
            <StyledInput label="Username" icon="👤"
              value={username} onChange={setUsername} placeholder="Enter username" />
          )}

          <StyledInput label="Password" icon="🔒"
            type="password"
            value={password} onChange={setPassword} placeholder="Enter your password" />
        </div>

        {/* 2FA notice badge */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 16px",
          background: "rgba(41,128,185,0.1)",
          border: "1px solid rgba(41,128,185,0.25)",
          borderRadius: TOKENS.radiusMd,
          marginTop: 20,
          marginBottom: 28,
        }}>
          <span style={{ fontSize: 18 }}>📱</span>
          <p style={{ fontSize: 12, color: "rgba(135,206,250,0.85)", lineHeight: 1.5 }}>
            A 2FA code from your authenticator app will be required after login.
          </p>
        </div>

        <GradientButton onClick={handleLogin} loading={loading} fullWidth>
          Sign In
        </GradientButton>

        <p style={{
          textAlign: "center", marginTop: 24,
          fontSize: 13, color: TOKENS.textSecondary,
        }}>
          New user?{" "}
          <a onClick={onSwitchToSignup} style={{
            color: TOKENS.accent, cursor: "pointer",
            textDecoration: "none", fontWeight: 600,
          }}>Create account →</a>
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: OTP Verification — step shown after password login
// ─────────────────────────────────────────────────────────────
function OTPView({ username, onSuccess, showToast }) {
  // Accepts a 6-digit OTP or recovery code to complete login
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const inputs = useRef([]);

  // Split OTP into 6 individual digit boxes for better UX
  const handleDigit = (idx, val) => {
    if (!/^\d?$/.test(val)) return;
    const arr = otp.padEnd(6, " ").split("");
    arr[idx] = val || " ";
    const next = arr.join("").trimEnd();
    setOtp(next);
    if (val && idx < 5) inputs.current[idx + 1]?.focus();
  };

  const handleVerify = () => {
    if (otp.length < 6) {
      showToast("Enter the complete 6-digit code.", "error"); return;
    }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      showToast(`Welcome, ${username}! 🎉`, "success");
      onSuccess();
    }, 700);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 56px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-fade" style={{ width: "100%", maxWidth: 380, textAlign: "center" }}>
        {/* Animated shield icon */}
        <div style={{
          width: 72, height: 72,
          borderRadius: "50%",
          background: "rgba(233,69,96,0.1)",
          border: "2px solid rgba(233,69,96,0.3)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 32, margin: "0 auto 24px",
          animation: "pulseGlow 2.5s ease infinite",
        }}>🛡️</div>

        <h2 style={{
          fontSize: 26, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 8,
        }}>Two-Factor Auth</h2>
        <p style={{
          fontSize: 14, color: TOKENS.textSecondary, marginBottom: 36, lineHeight: 1.6,
        }}>
          Open your authenticator app and enter the<br />6-digit code for{" "}
          <span style={{ color: TOKENS.accent, fontWeight: 600 }}>{username}</span>
        </p>

        {/* 6-box digit input */}
        <div style={{
          display: "flex", gap: 10, justifyContent: "center", marginBottom: 32,
        }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <input
              key={i}
              ref={el => (inputs.current[i] = el)}
              type="text"
              maxLength={1}
              value={otp[i] || ""}
              onChange={e => handleDigit(i, e.target.value)}
              onKeyDown={e => {
                if (e.key === "Backspace" && !otp[i] && i > 0)
                  inputs.current[i - 1]?.focus();
              }}
              style={{
                width: 46, height: 52,
                background: TOKENS.inputBg,
                border: `1.5px solid ${otp[i] ? TOKENS.accent : TOKENS.inputBorder}`,
                borderRadius: TOKENS.radiusMd,
                fontSize: 22, fontWeight: 700,
                color: TOKENS.textPrimary,
                textAlign: "center",
                outline: "none",
                fontFamily: "'JetBrains Mono', monospace",
                transition: TOKENS.transitionFast,
              }}
            />
          ))}
        </div>

        <GradientButton onClick={handleVerify} loading={loading} fullWidth>
          Verify Code
        </GradientButton>

        <p style={{
          fontSize: 12, color: TOKENS.textMuted, marginTop: 20,
        }}>
          Lost your device?{" "}
          <a href="#" style={{
            color: TOKENS.textSecondary, textDecoration: "underline",
          }}>Use a recovery code</a>
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: QRDisplay — 2FA setup after signup
// ─────────────────────────────────────────────────────────────
function QRDisplayView({ username, secret, recoveryCodes, onDone }) {
  // Shows mock QR code, secret key, and recovery codes after account creation
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    // Copy recovery codes to clipboard
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      flex: 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 40px",
      background: TOKENS.grad2,
      overflowY: "auto",
    }}>
      <div className="anim-fade" style={{ width: "100%", maxWidth: 400 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <h2 style={{
            fontSize: 24, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 8,
          }}>Set Up 2FA</h2>
          <p style={{ fontSize: 14, color: TOKENS.textSecondary, lineHeight: 1.6 }}>
            Scan this QR code with Google Authenticator or Authy
          </p>
        </div>

        {/* Mock QR code placeholder */}
        <div style={{
          background: "#fff",
          borderRadius: TOKENS.radiusLg,
          padding: 20,
          margin: "0 auto 24px",
          width: 180, height: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}>
          <div style={{
            width: 140, height: 140,
            background: `repeating-conic-gradient(#000 0% 25%, #fff 0% 50%)`,
            backgroundSize: "14px 14px",
            borderRadius: 4,
            opacity: 0.9,
          }} />
        </div>

        {/* Secret key display */}
        <div style={{
          background: "rgba(255,255,255,0.04)",
          border: `1px solid ${TOKENS.glassBorder}`,
          borderRadius: TOKENS.radiusMd,
          padding: "12px 16px",
          marginBottom: 20,
        }}>
          <p style={{ fontSize: 11, color: TOKENS.textMuted, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            🔑 Secret Key (manual entry)
          </p>
          <p style={{
            fontSize: 13, color: TOKENS.accent,
            fontFamily: "'JetBrains Mono', monospace",
            wordBreak: "break-all",
          }}>{secret || "JBSWY3DPEHPK3PXP"}</p>
        </div>

        {/* Recovery codes */}
        <div style={{
          background: "rgba(245,166,35,0.08)",
          border: "1px solid rgba(245,166,35,0.25)",
          borderRadius: TOKENS.radiusMd,
          padding: "14px 16px",
          marginBottom: 24,
        }}>
          <p style={{
            fontSize: 11, color: "#f5a623", marginBottom: 12,
            textTransform: "uppercase", letterSpacing: "0.08em",
          }}>
            🛡 Recovery Codes — Save These!
          </p>
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6,
          }}>
            {(recoveryCodes || ["ABC12345","DEF67890","GHI11223","JKL44556","MNO77889"]).map((c, i) => (
              <span key={i} style={{
                fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
                color: TOKENS.textPrimary,
                background: "rgba(255,255,255,0.06)",
                padding: "6px 10px",
                borderRadius: TOKENS.radiusSm,
                textAlign: "center",
              }}>{c}</span>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <GradientButton onClick={handleCopy} variant="secondary" fullWidth small>
            {copied ? "✓ Copied!" : "📋 Copy Codes"}
          </GradientButton>
          <GradientButton onClick={onDone} fullWidth small>
            Done ✓
          </GradientButton>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: CompanySettings — company info management panel
// ─────────────────────────────────────────────────────────────
function CompanySettingsView({ dbName, onSave, showToast }) {
  // Manages company profile including logo, contact info, and footer
  const [form, setForm] = useState({
    companyName: dbName?.replace(".db","").replace(/_/g," ") || "",
    phone: "", address: "", gst: "", footer: "",
    logoPreview: null,
  });
  const [loading, setLoading] = useState(false);
  const fileRef = useRef();
  const set = k => v => setForm(prev => ({ ...prev, [k]: v }));

  const handleLogoUpload = e => {
    // Read selected image file and display as preview
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => setForm(prev => ({ ...prev, logoPreview: ev.target.result }));
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      showToast("Company settings saved!", "success");
      onSave(form);
    }, 700);
  };

  return (
    <div style={{
      flex: 1, overflowY: "auto",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "40px 48px",
      background: TOKENS.grad2,
    }}>
      <div className="anim-left" style={{ width: "100%", maxWidth: 440 }}>
        <div style={{ marginBottom: 28 }}>
          <h2 style={{
            fontSize: 26, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 6,
          }}>🏢 Company Settings</h2>
          <p style={{ fontSize: 14, color: TOKENS.textSecondary }}>
            Configure your company profile and branding
          </p>
        </div>

        {/* Logo upload area */}
        <div style={{
          display: "flex", alignItems: "center", gap: 20, marginBottom: 28,
          padding: "20px",
          background: TOKENS.gradCard,
          border: `1.5px dashed ${TOKENS.glassBorder}`,
          borderRadius: TOKENS.radiusLg,
        }}>
          <div style={{
            width: 72, height: 72, borderRadius: TOKENS.radiusMd,
            background: TOKENS.glass,
            border: `1.5px solid ${TOKENS.glassBorder}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            overflow: "hidden", flexShrink: 0,
          }}>
            {form.logoPreview
              ? <img src={form.logoPreview} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              : <span style={{ fontSize: 28 }}>🏢</span>
            }
          </div>
          <div>
            <p style={{ fontSize: 13, fontWeight: 600, color: TOKENS.textPrimary, marginBottom: 8 }}>
              Company Logo
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <input ref={fileRef} type="file" accept="image/*"
                onChange={handleLogoUpload} style={{ display: "none" }} />
              <GradientButton onClick={() => fileRef.current.click()} variant="secondary" small>
                Upload
              </GradientButton>
              {form.logoPreview && (
                <GradientButton
                  onClick={() => setForm(p => ({ ...p, logoPreview: null }))}
                  variant="primary" small
                >
                  Remove
                </GradientButton>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <StyledInput label="Company Name" icon="🏢"
            value={form.companyName} onChange={set("companyName")} placeholder="Your company name" />
          <StyledInput label="Phone" icon="📞"
            value={form.phone} onChange={set("phone")} placeholder="+91 98765 43210" />
          <StyledInput label="Address" icon="📍"
            value={form.address} onChange={set("address")} placeholder="123 Business St, City" />
          <StyledInput label="GST Number" icon="🧾"
            value={form.gst} onChange={set("gst")} placeholder="22AAAAA0000A1Z5" />

          {/* Footer textarea */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{
              fontSize: 12, fontWeight: 500, letterSpacing: "0.08em",
              textTransform: "uppercase", color: TOKENS.textSecondary,
            }}>Footer Message</label>
            <textarea
              value={form.footer}
              onChange={e => set("footer")(e.target.value)}
              placeholder="Invoice footer, terms, or description..."
              rows={3}
              style={{
                background: TOKENS.inputBg,
                border: `1.5px solid ${TOKENS.inputBorder}`,
                borderRadius: TOKENS.radiusMd,
                padding: "12px 16px",
                fontSize: 14,
                color: TOKENS.textPrimary,
                fontFamily: "'Sora', sans-serif",
                resize: "vertical",
                outline: "none",
              }}
            />
          </div>
        </div>

        <div style={{ marginTop: 28 }}>
          <GradientButton onClick={handleSave} loading={loading} fullWidth>
            Save Settings
          </GradientButton>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  VIEW: Dashboard — post-login home screen
// ─────────────────────────────────────────────────────────────
function DashboardView({ username, dbName, onLogout }) {
  // Main dashboard shell shown after successful login
  const stats = [
    { label: "Users", value: "12", icon: "👥", change: "+3 this week" },
    { label: "Sessions", value: "847", icon: "⚡", change: "↑ 12% vs last month" },
    { label: "Security Events", value: "0", icon: "🛡️", change: "All clear" },
    { label: "Uptime", value: "99.9%", icon: "📈", change: "Last 30 days" },
  ];
  return (
    <div style={{
      minHeight: "100vh",
      background: TOKENS.grad1,
      fontFamily: "'Sora', sans-serif",
    }}>
      {/* Top navbar */}
      <nav style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "16px 40px",
        background: TOKENS.glass,
        backdropFilter: "blur(20px)",
        borderBottom: `1px solid ${TOKENS.glassBorder}`,
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 20 }}>⚡</span>
          <span style={{
            fontSize: 16, fontWeight: 700, letterSpacing: "0.08em",
            background: TOKENS.gradAccent,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>EVO AURA</span>
          <span style={{
            fontSize: 12, padding: "3px 10px",
            background: "rgba(233,69,96,0.12)",
            border: "1px solid rgba(233,69,96,0.3)",
            borderRadius: 50, color: TOKENS.accent,
          }}>{dbName?.replace(".db","")}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            background: TOKENS.gradBtn,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 700, color: "#fff",
          }}>
            {(username || "U")[0].toUpperCase()}
          </div>
          <span style={{ fontSize: 14, color: TOKENS.textSecondary }}>{username}</span>
          <button onClick={onLogout} style={{
            background: "transparent",
            border: `1px solid rgba(233,69,96,0.3)`,
            borderRadius: TOKENS.radiusSm,
            padding: "6px 14px", fontSize: 12,
            color: TOKENS.accent, cursor: "pointer",
            transition: TOKENS.transitionFast,
          }}>Sign Out</button>
        </div>
      </nav>

      <main style={{ padding: "40px" }}>
        <div className="anim-fade" style={{ marginBottom: 40 }}>
          <h1 style={{
            fontSize: 30, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 6,
          }}>
            Good morning, <span style={{
              background: TOKENS.gradAccent,
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>{username}</span> 👋
          </h1>
          <p style={{ fontSize: 15, color: TOKENS.textSecondary }}>
            Your workspace is secure and running smoothly.
          </p>
        </div>

        {/* Stats grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 20, marginBottom: 40,
        }}>
          {stats.map((s, i) => (
            <div key={i} className="anim-fade" style={{
              background: TOKENS.gradCard,
              border: `1px solid ${TOKENS.glassBorder}`,
              borderRadius: TOKENS.radiusLg,
              padding: "24px",
              backdropFilter: "blur(8px)",
              animationDelay: `${i * 0.07}s`,
              transition: TOKENS.transitionMed,
            }}
            onMouseEnter={e => e.currentTarget.style.transform = "translateY(-4px)"}
            onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}
            >
              <div style={{
                fontSize: 28, marginBottom: 12,
              }}>{s.icon}</div>
              <div style={{
                fontSize: 32, fontWeight: 700, color: TOKENS.textPrimary, marginBottom: 4,
              }}>{s.value}</div>
              <div style={{ fontSize: 12, color: TOKENS.textMuted, marginBottom: 4 }}>
                {s.label}
              </div>
              <div style={{ fontSize: 11, color: "#27ae60" }}>{s.change}</div>
            </div>
          ))}
        </div>

        {/* Quick actions */}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {[
            { label: "Manage Users", icon: "👥", desc: "Add, edit, or remove users" },
            { label: "Company Settings", icon: "🏢", desc: "Update company profile" },
            { label: "Security Log", icon: "🔐", desc: "View auth events" },
            { label: "Export Data", icon: "📤", desc: "Download reports" },
          ].map((a, i) => (
            <div key={i} style={{
              flex: "1 1 200px",
              background: TOKENS.gradCard,
              border: `1px solid ${TOKENS.glassBorder}`,
              borderRadius: TOKENS.radiusLg,
              padding: "20px",
              cursor: "pointer",
              transition: TOKENS.transitionMed,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = "rgba(233,69,96,0.4)";
              e.currentTarget.style.transform = "translateY(-3px)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = TOKENS.glassBorder;
              e.currentTarget.style.transform = "translateY(0)";
            }}>
              <div style={{ fontSize: 24, marginBottom: 10 }}>{a.icon}</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: TOKENS.textPrimary, marginBottom: 4 }}>
                {a.label}
              </div>
              <div style={{ fontSize: 12, color: TOKENS.textMuted }}>
                {a.desc}
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  SPLIT LAYOUT WRAPPER — left form + right company panel
// ─────────────────────────────────────────────────────────────
function SplitLayout({ leftView }) {
  // Renders the split-screen layout for auth pages
  return (
    <div style={{
      display: "flex",
      minHeight: "100vh",
      fontFamily: "'Sora', sans-serif",
    }}>
      {leftView}
      <CompanyPanel />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  ROOT APP — page router managing global view transitions
// ─────────────────────────────────────────────────────────────
export default function App() {
  // Central state machine: controls which view is active
  const [view, setView] = useState("askdb"); // askdb | startupauth | signup | login | otp | qr | settings | dashboard
  const [dbName, setDbName] = useState("");
  const [loggedUser, setLoggedUser] = useState(null);
  const [pendingUser, setPendingUser] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [toast, setToast] = useState(null);

  // Demo: start directly on login if db exists
  useEffect(() => {
    const saved = localStorage.getItem("evoaura_db");
    if (saved) { setDbName(saved); setView("login"); }
  }, []);

  // Show a temporary toast notification
  const showToast = (message, type = "info") => {
    setToast({ message, type });
  };

  // Animated page transition wrapper key forces remount
  const [transitionKey, setTransitionKey] = useState(0);
  const navigate = (v) => {
    setTransitionKey(k => k + 1);
    setView(v);
  };

  // ── Render the active view inside layout shell ──────────────
  const renderView = () => {
    // Views that use the split layout
    const splitViews = {
      askdb: (
        <AskDBNameView onNext={name => {
          setDbName(name);
          navigate("startupauth");
        }} />
      ),
      startupauth: (
        <StartupAuthView dbName={dbName} showToast={showToast} onSuccess={() => navigate("settings")} />
      ),
      signup: (
        <SignupView
          dbName={dbName} showToast={showToast}
          onSuccess={userData => {
            setPendingUser(userData);
            setQrData({ secret: "JBSWY3DPEHPK3PXP", codes: ["ABC12345","DEF67890","GHI11223","JKL44556","MNO77889"] });
            navigate("qr");
          }}
          onSwitchToLogin={() => navigate("login")}
        />
      ),
      login: (
        <LoginView
          dbName={dbName} users={["admin", "testuser"]}
          showToast={showToast}
          onSuccess={userData => {
            setPendingUser(userData);
            navigate("otp");
          }}
          onSwitchToSignup={() => navigate("signup")}
        />
      ),
      settings: (
        <CompanySettingsView
          dbName={dbName} showToast={showToast}
          onSave={() => {
            localStorage.setItem("evoaura_db", dbName);
            navigate("signup");
          }}
        />
      ),
      otp: (
        <OTPView
          username={pendingUser?.username}
          showToast={showToast}
          onSuccess={() => {
            setLoggedUser(pendingUser?.username);
            navigate("dashboard");
          }}
        />
      ),
      qr: (
        <QRDisplayView
          username={pendingUser?.username}
          secret={qrData?.secret}
          recoveryCodes={qrData?.codes}
          onDone={() => navigate("login")}
        />
      ),
    };

    if (view === "dashboard") {
      return (
        <DashboardView
          key={transitionKey}
          username={loggedUser}
          dbName={dbName}
          onLogout={() => { setLoggedUser(null); navigate("login"); }}
        />
      );
    }

    return (
      <SplitLayout key={transitionKey} leftView={splitViews[view]} />
    );
  };

  return (
    <>
      <GlobalStyles />
      {renderView()}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </>
  );
}