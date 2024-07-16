// app/ui/components/ScoreCard.tsx
'use client';

interface ScoreCardProps {
    score: any;
    onContinue: () => void;
    onFinishLesson: () => void;
}

const ScoreCard: React.FC<ScoreCardProps> = ({ score, onContinue, onFinishLesson }) => {
    return (
        <div className="max-w-md w-full bg-white p-8 rounded shadow">
            <h2 className="text-2xl font-bold mb-4">Task Score</h2>
            <pre className="mb-4">{JSON.stringify(score, null, 2)}</pre>
            <button
                onClick={onContinue}
                className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline mb-4"
            >
                Continue
            </button>
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
