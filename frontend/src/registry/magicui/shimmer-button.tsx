import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import clsx from "clsx";

type ShimmerButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  loading?: boolean;
  block?: boolean;
  iconStart?: ReactNode;
  iconEnd?: ReactNode;
};

export const ShimmerButton = forwardRef<HTMLButtonElement, ShimmerButtonProps>(
  function ShimmerButton(
    {
      className,
      children,
      type = "button",
      disabled,
      loading = false,
      block = false,
      iconStart,
      iconEnd,
      ...rest
    },
    ref,
  ) {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        className={clsx("shimmer-button", block && "btn-block", className)}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        {...rest}
      >
        <span className="shimmer-button__shine" aria-hidden="true" />
        <span className="shimmer-button__content">
          {loading ? <span className="btn-spinner" aria-hidden="true" /> : iconStart}
          <span>{children}</span>
          {!loading && iconEnd}
        </span>
      </button>
    );
  },
);
