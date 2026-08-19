import styles from "@/styles/wizard/wizard.module.css";

export default function RequiredMark() {
  return (
    <span className={styles.requiredMark} aria-hidden="true">
      *
    </span>
  );
}
