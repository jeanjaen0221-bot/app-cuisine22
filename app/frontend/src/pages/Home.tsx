import ReservationList from '../components/ReservationList'
import ReminderBanner from '../components/ReminderBanner'

type Props = { onReminderCount?: (count: number) => void }

export default function Home({ onReminderCount }: Props) {
  return (
    <div className="container space-y-4">
      <ReminderBanner onCountChange={onReminderCount} />
      <ReservationList />
    </div>
  )
}
