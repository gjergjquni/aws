export interface User {
  id: string;
  name: string;
  email: string;
  role: "investigator" | "admin";
  initials: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  remember?: boolean;
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
}

export interface AuthSession {
  user: User;
  token: string;
}
