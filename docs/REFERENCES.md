# Historical reference inventory and workflow mapping

The user supplied the following guides during implementation. Their text and embedded historical screens describe legacy behavior; they do not provide original application code, a database schema or executable tests. The dates below are the versions printed on the supplied documents, not a statement that the rules remain current.

| Reference | Supplied document | Evidence used |
|---|---|---|
| G-02 | *Welcome to PermitsNJ*, version 08-19-2004, 1 page | Internet-based application, inspection/certification/calculation/reporting purpose; MyNewJersey and authentication-code access; role-dependent menus; Add/Edit/printing and setup topics |
| S-01 | *PermitsNJ Set-Up — Reference Tables*, version 01-17-2007, 1 page | Required/optional setup and entity/role control for reference tables; DCA-maintained versus municipality-maintained inputs |
| S-02 | *PermitsNJ Set-Up — Create and Maintain Fee Schedules*, version 08-15-2009, 10 pages | Five subcodes, UCC template/line order, effective dates, minima/maxima, tier/basis/group data, review/activation, third-party and DCA-derived rates, copy-and-add versions |

These guides are the source for the **documented** column below. A feature being documented here does not mean its full legacy behavior has been reproduced.

## G-02 access and navigation

| Documented workflow | Demonstration mapping | Gap / dependency |
|---|---|---|
| MyNewJersey registration and authentication code | Local password/session authentication for synthetic accounts | Portal API, approved integration, identity lifecycle and codes not supplied; no portal parity |
| Role controls visible functions | Five demonstration roles with server-side municipality and ownership checks | Historical role matrix, entity hierarchy and role-manager rules not supplied |
| Left Main Menu with Add/Edit functions | Responsive navigation with list/detail/create/edit actions | Modern interaction mapping; exact legacy screens are not reproduced |
| Applications, inspections, certificates, calculations and reports | Runnable demo workflows and sample fee rules | Historical guide only names these capabilities; detailed official workflow rules remain unverified |
| Local Role Manager manages users | Host-admin management CLI creates initial users | Browser user administration, delegation and production identity lifecycle deferred |

## S-01 reference-table inventory

| Documented table | Documented ownership / input | Demonstration mapping and outstanding work |
|---|---|---|
| Additional Fees | Required initial setup; DCA basic list; some rates DCA-controlled; local additions require ordinance | Inventory only; no official surcharge list/feed or ordinance validation |
| Architects/Engineers | Optional, records may be added during application | Not yet modeled; no fictitious professional registry implied |
| Block/Lot | Preloaded from Taxation/local assessor data; local edits do not routinely update assessor records | Work-site address only; no parcel import, assessor data or writeback |
| Contractors | DCA conversion of local UCCARS contractor file; ongoing application additions | Synthetic directory list/create; no UCCARS conversion or license verification |
| Building Fee Schedules | Required; separate schedules where ordinance varies by use group | Partial version lifecycle; sample application calculation is separate; use-group engine deferred |
| Electrical Fee Schedules | Required | Partial version lifecycle; official UCC lines/rates not supplied |
| Elevator Fee Schedules | Required | Partial version lifecycle; elevator permit technical application/calculation not implemented |
| Fire Protection Fee Schedules | Required | Partial version lifecycle; fire technical application/calculation not implemented |
| Plumbing Fee Schedules | Required | Partial version lifecycle; official UCC lines/rates not supplied |
| Inspection Types | Preloaded and DCA-maintained | Generic demo inspection/result; no official type feed |
| Interlocal Offices | Preloaded and DCA-maintained | Inventoried only; no authority/office hierarchy integration |
| Municipalities | Basic record preloaded; local office/address/appeals details required for printed output | Synthetic municipality names and scoping; official office and appeals metadata deferred |
| Prior Approvals | Preloaded and DCA-maintained | Boolean demonstration prerequisite; official approval catalog and per-approval evidence deferred |
| Staff | Required officials, technical assistants, subcode officials and inspectors; scheduling/results/notices depend on it | Synthetic role-bearing users and assigned inspectors; full official staffing records/delegations deferred |
| State Offices | Preloaded and DCA-maintained | Inventoried only; no live list |
| Use Groups | Preloaded and DCA-maintained | Inventoried only; no regulatory classification engine |
| Third Party Agencies | Preloaded and DCA-maintained | Inventoried only; no agency registry/contracts or provider connection |

Municipality-level isolation is implemented for operational records. The guide's broader **entity-level** hierarchy is not established by these materials and is not fabricated.

## S-02 fee-maintenance workflow

| Documented rule / workflow | Planned demonstration mapping | Remaining boundary |
|---|---|---|
| Select subcode and municipality | Municipality-scoped schedules for Building, Electrical, Elevator, Fire Protection and Plumbing | No DCA/agency entity hierarchy |
| Begin with UCC template; line items correspond to technical sections | Explicit demo line items with preserved sequence and zero amounts | Authoritative complete UCC template not supplied; never label the demo lines official |
| Enter effective date; schedule min/max | Store versioned schedule metadata, ordinance citation and optional min/max cents | Complete statutory calculation semantics need approved specification |
| Description, basis, line minimum and tiers with From/To/Amount/Increment/Per | Demo description, line minimum and explicit fixed/per-unit basis | S-A2 Fee Basis Chart absent; full basis/tier engine is not invented |
| Optional “Show 2 Input Fields” | Deferred with technical line-item form model | Need complete input semantics and calculation examples |
| Quantity Range/Flat Fee Range groups | Deferred | Need S-A2 definitions and test examples |
| Append custom items consecutively; keep zero-fee items | Demo maintenance retains ordered items | Need official UCC ordering and local ordinance to validate real items |
| Save, print, compare to worksheet, confirm then activate | Partial lifecycle: saved drafts, printable schedule, explicit review confirmation and activation | Human review cannot be proven from a browser print action; demonstration is not ordinance approval |
| Copy and Add for amended ordinance/new effective date | Create a new version from a prior schedule | Historical values retained; no promise of official automatic assessment behavior |
| Copy and Add UCC Items | Deferred | Authoritative UCC template absent |
| Third-party percent of state fees plus administrative surcharge at most 15% | Documented requirement and limitation | DCA fee source, contract, current statute confirmation and calculation integration unavailable |
| 100% state fees; clear field to make local changes | Deferred | No authoritative state-rate feed; sample data cannot substitute for it |

Fee-schedule maintenance is a partial workflow separate from the provisional building/electrical/plumbing fee calculation used on permits. Activating a demonstration schedule must not be presented as reproducing the historical automatic fee engine.

## Focused follow-up inputs

To implement the documented fee engine accurately, supply the current municipality ordinance, UCC line-item template, S-A1 worksheets, S-A2 Fee Basis Chart and expected calculation examples. For reference-table/identity parity, supply entity/role policies, current DCA datasets/API contracts, staffing fields and MyNewJersey integration documentation. For permit lifecycle parity, supply detailed application, inspection, certificate, notice/order and reporting guides and approved document samples.
