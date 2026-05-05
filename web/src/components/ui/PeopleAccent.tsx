export type PeopleAccentName = "coffee" | "goodnight" | "inspired" | "music" | "notes" | "reading" | "thinking" | "working_laptop";

const PEOPLE_ACCENT_SRC: Record<PeopleAccentName, string> = {
  coffee: "/illustrations/notion-people/coffee.svg",
  goodnight: "/illustrations/notion-people/goodnight.svg",
  inspired: "/illustrations/notion-people/inspired.svg",
  music: "/illustrations/notion-people/music.svg",
  notes: "/illustrations/notion-people/notes.svg",
  reading: "/illustrations/notion-people/reading.svg",
  thinking: "/illustrations/notion-people/thinking.svg",
  working_laptop: "/illustrations/notion-people/working_laptop.svg",
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
