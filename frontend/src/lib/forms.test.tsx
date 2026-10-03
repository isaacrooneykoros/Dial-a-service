import { render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/errors";
import { applyFieldErrors } from "@/lib/forms";

interface Values {
  phone: string;
  password: string;
}

const serverError = new ApiError({
  status: 400,
  code: "validation_error",
  message: "Some details need fixing. Check the highlighted fields.",
  fields: {
    password: ["This password is too common."],
    phone: ["Enter a Kenyan mobile number."],
    non_field_errors: ["Something else."],
  },
});

function Form({ onUnmatched }: { onUnmatched: (messages: string[]) => void }) {
  const {
    register,
    setError,
    formState: { errors },
  } = useForm<Values>({ defaultValues: { phone: "0712", password: "password1" } });
  useEffect(() => {
    onUnmatched(applyFieldErrors(serverError, setError, ["phone", "password"]));
  }, [setError, onUnmatched]);
  return (
    <form>
      <input aria-label="phone" {...register("phone")} />
      <p>{errors.phone?.message}</p>
      <input aria-label="password" {...register("password")} />
      <p>{errors.password?.message}</p>
    </form>
  );
}

describe("applyFieldErrors", () => {
  it("shows messages under fields, focuses the first in form order and keeps the input", async () => {
    const onUnmatched = vi.fn();
    render(<Form onUnmatched={onUnmatched} />);

    expect(await screen.findByText("Enter a Kenyan mobile number.")).toBeInTheDocument();
    expect(screen.getByText("This password is too common.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("phone")).toHaveFocus());
    expect(screen.getByLabelText("phone")).toHaveValue("0712");
    expect(screen.getByLabelText("password")).toHaveValue("password1");
    expect(onUnmatched).toHaveBeenCalledWith(["Something else."]);
  });
});
