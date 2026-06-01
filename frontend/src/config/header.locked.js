// ============================================================================
//  ██╗      ██████╗  ██████╗██╗  ██╗███████╗██████╗
//  ██║     ██╔═══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
//  ██║     ██║   ██║██║     █████╔╝ █████╗  ██║  ██║
//  ██║     ██║   ██║██║     ██╔═██╗ ██╔══╝  ██║  ██║
//  ███████╗╚██████╔╝╚██████╗██║  ██╗███████╗██████╔╝
//  ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝
//
//  ⚠  HEADER LAYOUT LOCKED — DO NOT EDIT WITHOUT EXPLICIT USER APPROVAL  ⚠
//
//  These values were dialed in by the product owner on 2026-06-01 and signed
//  off as final. They control the Header (logo + burger + A/C/M chips) and
//  the vertical breathing room around it.
//
//  DO NOT change any value below unless the user explicitly asks for it.
//  If you (a future AI agent or developer) feel the urge to "improve" these,
//  STOP. Ask the user first.
//
//  The PNG asset itself is also fixed:
//    /app/frontend/public/nxt8-logo.png  — must remain tight-cropped (no
//    transparent padding), otherwise CSS margins won't work as intended.
// ============================================================================

export const HEADER_LOCKED = Object.freeze({
  // Tailwind class for the logo <img> height. h-4 = 16px.
  logoHeightClass: "h-4",

  // Negative-left margin: bleeds the logo past the container's left padding
  // so it sits flush against the screen edge.
  logoMarginLeftClass: "-ml-6",

  // Vertical padding on the <header> element itself.
  headerVerticalPaddingClass: "py-0",

  // Padding above the Header inside app-shell (App.js → app-shell-header).
  shellTopPaddingClass: "pt-0",

  // Padding above/below the home view wrapper directly under the header.
  homeViewPaddingClass: "pt-0 pb-4",

  // The PNG file used as the logotype. Must be alpha-cropped to the
  // visible glyphs (no transparent canvas padding).
  logoSrc: "/nxt8-logo.png",

  // Sentinel string future agents can grep for before editing.
  __lock: "HEADER_LAYOUT_LOCKED_2026_06_01",
});
