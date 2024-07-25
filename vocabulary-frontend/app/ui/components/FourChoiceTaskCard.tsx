// app/ui/components/FourChoiceTaskCard.tsx
'use client';

import { Task } from '@/app/lib/definitions';
import { useState } from 'react';

interface FourChoiceTaskCardProps {
    task: Task;
    onSubmit: (answer: string) => void;
}

const FourChoiceTaskCard: React.FC<FourChoiceTaskCardProps> = ({ task, onSubmit }) => {
    const [selectedAnswer, setSelectedAnswer] = useState<string>('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit(selectedAnswer);
    };

    return (
        <div className="max-w-md w-full bg-white p-8 rounded shadow">
            <p className="mb-4">{task.task_string}</p>
            <form onSubmit={handleSubmit}>
                <div className="mb-4">
                    {['A', 'B', 'C', 'D'].map((key) => (
                        <div key={key} className="mb-2">
                            <label className="inline-flex items-center">
                                <input
                                    type="radio"
                                    name="answer"
                                    value={key}
                                    checked={selectedAnswer === key}
                                    onChange={(e) => setSelectedAnswer(e.target.value)}
                                    className="form-radio text-blue-500"
                                    required
                                />
                                <span className="ml-2">{task.resources[key].resource}</span>
                            </label>
                        </div>
                    ))}
                </div>
                <button
                    type="submit"
                    className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                >
                    Submit
                </button>
            </form>
        </div>
    );
};

export default FourChoiceTaskCard;
