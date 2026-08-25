import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useChatInputHistory } from "./use-chat-input-history";

const setInputValueAndCaret = (value: string, offset = value.length) => {
  const element = document.createElement("div");
  const textNode = document.createTextNode(value);
  element.appendChild(textNode);

  // jsdom does not calculate innerText like a browser does for detached nodes.
  Object.defineProperty(element, "innerText", {
    configurable: true,
    get: () => element.textContent ?? "",
  });

  document.body.appendChild(element);

  const selection = window.getSelection();
  const range = document.createRange();
  range.setStart(textNode, offset);
  range.collapse(true);
  selection?.removeAllRanges();
  selection?.addRange(range);
  return element;
};

describe("useChatInputHistory", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.body.innerHTML = "";
  });

  it("navigates backward and forward while restoring the draft", () => {
    const { result } = renderHook(() => useChatInputHistory("conversation-1"));

    act(() => {
      result.current.record("first prompt");
      result.current.record("second prompt");
    });

    let input = setInputValueAndCaret("current draft");
    expect(result.current.navigate(input, "backward")).toBe("second prompt");

    input = setInputValueAndCaret("second prompt");
    expect(result.current.navigate(input, "backward")).toBe("first prompt");

    input = setInputValueAndCaret("first prompt");
    expect(result.current.navigate(input, "forward")).toBe("second prompt");

    input = setInputValueAndCaret("second prompt");
    expect(result.current.navigate(input, "forward")).toBe("current draft");
  });

  it("does not navigate when the caret is not at a boundary", () => {
    const { result } = renderHook(() => useChatInputHistory("conversation-1"));

    act(() => {
      result.current.record("first prompt");
    });

    const input = setInputValueAndCaret("draft text", 3);
    expect(result.current.navigate(input, "backward")).toBeUndefined();
    expect(result.current.navigate(input, "forward")).toBeUndefined();
  });

  it("deduplicates consecutive prompts and scopes storage by conversation", () => {
    const first = renderHook(() => useChatInputHistory("conversation-1"));
    const second = renderHook(() => useChatInputHistory("conversation-2"));

    act(() => {
      first.result.current.record("same prompt");
      first.result.current.record("same prompt");
      second.result.current.record("other prompt");
    });

    const firstInput = setInputValueAndCaret("");
    expect(first.result.current.navigate(firstInput, "backward")).toBe(
      "same prompt",
    );

    const secondInput = setInputValueAndCaret("");
    expect(second.result.current.navigate(secondInput, "backward")).toBe(
      "other prompt",
    );
  });
});
