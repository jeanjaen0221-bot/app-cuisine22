import ReservationList from '../components/ReservationList'
import ReminderBanner from '../components/ReminderBanner'

export default function Home() {
  return (
    <div className="container space-y-4">
      <ReminderBanner />
      <ReservationList />
    </div>
  )
}
