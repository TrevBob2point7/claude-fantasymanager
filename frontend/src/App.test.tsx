import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("renders Fantasy Manager heading on login page", () => {
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByText("Fantasy Manager")).toBeInTheDocument();
});
