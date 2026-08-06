// @vitest-environment jsdom

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TurnstileWidget } from "./TurnstileWidget";

describe("TurnstileWidget mobile recovery", () => {
  afterEach(() => {
    delete window.turnstile;
  });

  it("shows the Cloudflare error code and lets the visitor retry", async () => {
    let errorCallback: ((code: string) => void) | undefined;
    const reset = vi.fn();
    window.turnstile = {
      render: vi.fn((_container, options) => {
        errorCallback = options["error-callback"];
        return "widget-mobile";
      }),
      remove: vi.fn(),
      reset
    };

    render(
      <TurnstileWidget
        siteKey="1x00000000000000000000AA"
        action="register"
        onTokenChange={vi.fn()}
      />
    );
    await act(async () => undefined);
    act(() => errorCallback?.("200500"));

    expect(screen.getByRole("alert").textContent).toContain("200500");
    await userEvent.click(screen.getByRole("button", { name: "重新验证" }));
    expect(reset).toHaveBeenCalledWith("widget-mobile");
  });
});
