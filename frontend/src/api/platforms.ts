import { get, post, del } from "./client";
import type {
  PlatformAccount,
  CreatePlatformAccountRequest,
} from "./types";

export function getPlatformAccounts(): Promise<PlatformAccount[]> {
  return get<PlatformAccount[]>("/platforms/accounts");
}

export function createPlatformAccount(
  data: CreatePlatformAccountRequest,
): Promise<PlatformAccount> {
  return post<PlatformAccount>("/platforms/accounts", data);
}

export function deletePlatformAccount(accountId: string): Promise<void> {
  return del<void>(`/platforms/accounts/${accountId}`);
}
