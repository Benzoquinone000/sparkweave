export type PeopleAccentName =
  | "course_map"
  | "learner_profile"
  | "knowledge_notes"
  | "writing_board"
  | "vision_tutor"
  | "question_lab"
  | "playground_lab"
  | "settings_panel"
  | "coffee"
  | "goodnight"
  | "inspired"
  | "music"
  | "notes"
  | "reading"
  | "thinking"
  | "working_laptop";

const PEOPLE_ACCENT_SRC: Record<PeopleAccentName, string> = {
  course_map: "/illustrations/education/course-map.svg",
  learner_profile: "/illustrations/education/learner-profile.svg",
  knowledge_notes: "/illustrations/education/knowledge-notes.svg",
  writing_board: "/illustrations/education/writing-board.svg",
  vision_tutor: "/illustrations/education/vision-tutor.svg",
  question_lab: "/illustrations/education/question-lab.svg",
  playground_lab: "/illustrations/education/playground-lab.svg",
  settings_panel: "/illustrations/education/settings-panel.svg",
  coffee: "/illustrations/education/settings-panel.svg",
  goodnight: "/illustrations/education/course-map.svg",
  inspired: "/illustrations/education/question-lab.svg",
  music: "/illustrations/education/playground-lab.svg",
  notes: "/illustrations/education/knowledge-notes.svg",
  reading: "/illustrations/education/knowledge-notes.svg",
  thinking: "/illustrations/education/learner-profile.svg",
  working_laptop: "/illustrations/education/writing-board.svg",
};

export function PeopleAccent({ name, className = "" }: { name: PeopleAccentName; className?: string }) {
  return (
    <img
      src={PEOPLE_ACCENT_SRC[name]}
      alt=""
      aria-hidden="true"
      draggable={false}
      className={`dt-notion-sticker pointer-events-none select-none ${className}`}
    />
  );
}

export function PeopleAccentStrip({
  name,
  title,
  helper,
}: {
  name: PeopleAccentName;
  title: string;
  helper: string;
}) {
  return (
    <div className="relative min-h-[132px] overflow-hidden border-b border-line bg-[#fbfbfa]">
      <div className="relative z-10 max-w-[220px] px-4 py-4">
        <p className="text-sm font-semibold text-ink">{title}</p>
        <p className="mt-1 text-xs leading-5 text-steel">{helper}</p>
      </div>
      <PeopleAccent name={name} className="absolute bottom-[-28px] right-[-14px] h-44 w-52 opacity-95" />
    </div>
  );
}
