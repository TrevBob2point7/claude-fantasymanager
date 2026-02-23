import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "./App";

test("renders Fantasy Manager heading", () => {
  render(<App />);
  expect(screen.getByText("Fantasy Manager")).toBeInTheDocument();
});
