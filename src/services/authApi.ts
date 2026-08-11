import { defaultUser, demoCredentials } from "@/data/users";
import { STORAGE_KEYS } from "@/lib/constants";
import type { AuthSession, LoginCredentials, RegisterInput, User } from "@/types";

function delay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.authSession);
    if (!raw) return null;
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

function writeSession(session: AuthSession | null): void {
  if (session) {
    localStorage.setItem(STORAGE_KEYS.authSession, JSON.stringify(session));
  } else {
    localStorage.removeItem(STORAGE_KEYS.authSession);
  }
}

export const authApi = {
  async getSession(): Promise<AuthSession | null> {
    await delay(50);
    return readSession();
  },

  async login(credentials: LoginCredentials): Promise<AuthSession> {
    await delay(600);

    if (
      credentials.email !== demoCredentials.email ||
      credentials.password !== demoCredentials.password
    ) {
      throw new Error("Invalid email or password");
    }

    const session: AuthSession = {
      user: { ...defaultUser, email: credentials.email },
      token: `mock-token-${Date.now()}`,
    };

    writeSession(session);
    return session;
  },

  async register(input: RegisterInput): Promise<AuthSession> {
    await delay(600);

    const user: User = {
      id: `user-${Date.now()}`,
      name: input.name,
      email: input.email,
      role: "investigator",
      initials: input.name
        .split(" ")
        .map((part) => part[0])
        .join("")
        .slice(0, 2)
        .toUpperCase(),
    };

    const session: AuthSession = {
      user,
      token: `mock-token-${Date.now()}`,
    };

    writeSession(session);
    return session;
  },

  async logout(): Promise<void> {
    await delay(100);
    writeSession(null);
  },
};
