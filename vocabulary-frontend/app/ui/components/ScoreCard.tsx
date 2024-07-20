// app/ui/components/ScoreCard.tsx
'use client';

import { Score } from "@/app/lib/definitions";

interface ScoreCardProps {
    score: Score[];
    hasNextTask: boolean;
    onContinue: () => void;
    onFinishLesson: () => void;
}

const ScoreCard: React.FC<ScoreCardProps> = ({ score, hasNextTask, onContinue, onFinishLesson }) => {
    return (
        <div className="max-w-md w-full bg-white p-8 rounded shadow">
            <h2 className="text-2xl font-bold mb-4">Task Score</h2>
            <ul className="mb-4">
                {score.map((item) => (
                    <li key={item.word.id} className="flex justify-between">
                        <span>{item.word.item}</span>
                        <span>{item.score}</span>
                    </li>
                ))}
            </ul>
            {hasNextTask ? (
                <button
                    onClick={onContinue}
                    className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline mb-4"
                >
                    Continue
                </button>
                ) : null
            }
            <button
                onClick={onFinishLesson}
                className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
            >
                Finish Lesson
            </button>
        </div>
    );
};

export default ScoreCard;
