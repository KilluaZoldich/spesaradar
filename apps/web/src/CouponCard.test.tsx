import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import CouponCard from "./CouponCard";
import { couponFixture } from "./coupon.fixture";
afterEach(() => vi.useRealTimers());
it("mostra beneficio, due finestre e minima spesa senza prezzo prodotto", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-08T10:00:00Z"));
  const { container } = render(<CouponCard coupon={couponFixture} />);
  expect(screen.getByRole("heading")).toHaveTextContent("10,00 € di buono");
  expect(screen.getByText(/20 settembre 2026/)).toBeVisible();
  expect(screen.getByText(/7 ottobre 2026/)).toHaveTextContent("30,00 €");
  expect(screen.getByText(/digitale da attivare/)).toBeVisible();
  expect(container.querySelector(".offer-card")).toBeNull();
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "https://fixture.invalid/voucher",
  );
});
it("dopo ottenimento finito indica solo uso di buoni già ricevuti", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-21T10:00:00Z"));
  render(<CouponCard coupon={couponFixture} />);
  expect(screen.getByText(/Ottenimento terminato/)).toBeVisible();
  expect(screen.queryByText(/ottieni un buono/)).not.toBeInTheDocument();
});
