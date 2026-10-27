# conversation-resilience — builder's notes beside the sealed contract

- Deviation (2026-10-27): `#talk-resume` is an icon button (icon `play`, `aria-label="Торкніться, щоб продовжити"`),
  not a button with words as the contract's Seam wrote. Why: the owner's rule of task 207 — every button of the pages is
  an icon with no words and a name for screen readers (`tests/web/test_icon_buttons.py`); an owner's decision outranks
  the contract's wording. Behaviour is the same: hidden until `resume()` without a tap failed, a tap resumes.
