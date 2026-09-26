"""The AI Intake (asset-model-revision §23): guided, AI-assisted entry of
assets, tickets and documents.

Two halves, deliberately separable:

* `guide` checks a draft deterministically and says what to do next. It
  needs no model, so it works in every workspace, and it is what keeps an
  entry correct whether or not a model helped write it.
* `assist` asks the model to fill a draft from what the person describes
  or photographs. Everything it returns is a suggestion with its evidence;
  nothing is saved until the person saves the form, and `outcome` then
  records what they kept and what they corrected.
"""
