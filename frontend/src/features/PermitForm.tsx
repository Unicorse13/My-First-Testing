import { useEffect, useState } from "react";
import { api, text, type Config, type Row, type Permit } from "../api";
import { ErrorBox, Loading, Modal, type Field, Form } from "../components/ui";

export default function PermitForm({
  config,
  permit,
  onClose,
  onSaved,
}: {
  config: Config;
  permit?: Permit;
  onClose: () => void;
  onSaved: (id: number) => void;
}) {
  const [applicants, setApplicants] = useState<Row[]>([]),
    [contractors, setContractors] = useState<Row[]>([]),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Row[]>("/applicants"), api<Row[]>("/contractors")])
      .then(([a, c]) => {
        setApplicants(a);
        setContractors(c);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, []);
  const fields: Field[] = [
    {
      name: "type",
      label: "Permit type",
      required: true,
      options: config.permit_types.map((t) => ({
        value: text(t.code),
        label: text(t.label),
      })),
      value: permit?.type || "building",
    },
    {
      name: "applicant_id",
      label: "Applicant",
      required: true,
      options: applicants.map((a) => ({ value: a.id, label: text(a.name) })),
      value: permit?.applicant_id || applicants[0]?.id,
    },
    {
      name: "work_address",
      label: "Work-site address",
      required: true,
      wide: true,
      value: permit?.work_address,
    },
    {
      name: "description",
      label: "Description of proposed work",
      type: "textarea",
      required: true,
      wide: true,
      value: permit?.description,
    },
    {
      name: "contractor_id",
      label: "Contractor (optional)",
      options: contractors.map((c) => ({ value: c.id, label: text(c.name) })),
      value: permit?.contractor_id ?? "",
    },
    {
      name: "area_sqft",
      label: "Work area (square feet)",
      type: "number",
      min: 0,
      max: 1000000,
      step: "1",
      required: true,
      value: permit?.area_sqft ?? 0,
      help: "Active matching fee schedules take precedence. Demo fallback: building $150 + $0.25/sq ft; electrical $75; plumbing $90. Other types require a configured schedule.",
    },
    {
      name: "use_group",
      label: "Use group (optional)",
      value: String(permit?.use_group ?? ""),
      help: "Must match the schedule use group exactly; leave blank for the default schedule.",
    },
    {
      name: "prior_approval",
      label: "Prior approvals have been obtained",
      type: "checkbox",
      value: Boolean(permit?.prior_approval),
      wide: true,
      help: "Required before submitting the application. This is a demonstration rule.",
    },
  ];
  return (
    <Modal
      title={permit ? `Edit ${permit.number}` : "New permit application"}
      onClose={onClose}
    >
      <ErrorBox message={error} />
      {!loaded ? (
        <Loading />
      ) : (
        <Form
          fields={fields}
          submitLabel={permit ? "Save permit" : "Create draft permit"}
          onCancel={onClose}
          onSubmit={async (v) => {
            const p = await api<Permit>(
              permit ? `/permits/${permit.id}` : "/permits",
              permit ? "PATCH" : "POST",
              {
                ...v,
                applicant_id: Number(v.applicant_id),
                contractor_id: v.contractor_id ? Number(v.contractor_id) : null,
                area_sqft: Number(v.area_sqft),
              },
            );
            onSaved(p.id);
          }}
        />
      )}
    </Modal>
  );
}
