import { expect, test } from "vitest";

import { APP_NAME } from "./placeholder";

test("exposes the app name", () => {
  expect(APP_NAME).toBe("Fernway Market");
});
