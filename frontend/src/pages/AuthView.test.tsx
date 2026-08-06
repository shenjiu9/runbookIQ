// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthView } from "./AuthView";
import {
  acceptInvitation,
  fetchSecurityConfig,
  previewInvitation
} from "../api";

vi.mock("../api", () => ({
  acceptInvitation: vi.fn(),
  fetchSecurityConfig: vi.fn(),
  login: vi.fn(),
  previewInvitation: vi.fn(),
  register: vi.fn()
}));

describe("AuthView invitation acceptance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/#invite=mobile-invite-token");
  });

  it("lets an invited user accept even while registration security config is unavailable", async () => {
    vi.mocked(previewInvitation).mockResolvedValue({
      email: "member@example.com",
      role: "viewer",
      organization_name: "移动端测试企业",
      organization_url: "https://knowledge.example.com",
      expires_at: "2026-08-13T00:00:00Z"
    });
    vi.mocked(fetchSecurityConfig).mockReturnValue(new Promise(() => undefined));
    vi.mocked(acceptInvitation).mockResolvedValue({
      user: { id: "user-mobile", email: "member@example.com" },
      organization: {
        id: "org-mobile",
        name: "移动端测试企业",
        slug: "mobile",
        url: "https://knowledge.example.com",
        branding: {
          display_name: "移动端测试企业",
          logo_url: null,
          primary_color: "#0F766E",
          welcome_title: "欢迎",
          welcome_message: "欢迎进入企业知识空间"
        }
      },
      role: "viewer"
    });
    const authenticated = vi.fn();
    const user = userEvent.setup();

    render(<AuthView onAuthenticated={authenticated} />);

    await screen.findByText("member@example.com");
    await user.type(screen.getByLabelText("密码"), "Mobile-password-2026");
    await user.type(screen.getByLabelText("确认密码"), "Mobile-password-2026");
    const submit = screen.getByRole("button", { name: "接受邀请并进入" });

    expect((submit as HTMLButtonElement).disabled).toBe(false);
    await user.click(submit);
    await waitFor(() => expect(acceptInvitation).toHaveBeenCalledWith(
      "mobile-invite-token",
      "Mobile-password-2026"
    ));
    expect(authenticated).toHaveBeenCalledOnce();
  });
});
