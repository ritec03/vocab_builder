// app/ui/components/TaskCard.tsx
'use client';

import { useState } from 'react';

interface Task {
    id: number;
    task_string: string;
    template: {
        id: number;
        template: string;
        task_type: string;
        starting_language: string;
        target_language: string;
    };
    correctAnswer: string;
    resources: {
        id: number;
        resource: string;
        target_words: {
            id: number;
            item: string;
            pos: string;
            freq: number;
        }[];
    }[];
    learning_items: {
        id: number;
        item: string;
        pos: string;
        freq: number;
    }[];
}

interface TaskCardProps {
    task: Task;
    onSubmit: (answer: string) => void;
}

const TaskCard: React.FC<TaskCardProps> = ({ task, onSubmit }) => {
    const [answer, setAnswer] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit(answer);
    };

    return (
        <div className="max-w-md w-full bg-white p-8 rounded shadow">
            <h2 className="text-2xl font-bold mb-4">{task.template.task_type}</h2>
            <p className="mb-4">{task.task_string}</p>
            <form onSubmit={handleSubmit}>
                <div className="mb-4">
                    <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="answer">
                        Your Answer
                    </label>
                    <input
                        type="text"
                        id="answer"
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                        required
                    />
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

export default TaskCard;
