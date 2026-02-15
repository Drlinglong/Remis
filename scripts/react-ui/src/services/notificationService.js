import { toast } from 'react-hot-toast';

const notificationService = {
  // A mapping from style to toast options
  styleOptions: {
    'minimal': {},
    'bottom-right': { duration: Infinity },
    'sidebar': {},
  },

  /**
   * Triggers a success notification.
   * @param {string} message The message to display.
   * @param {string} notificationStyle The current notification style from context.
   */
  success(message, notificationStyle) {
    const options = this.styleOptions[notificationStyle] || {};
    toast.success(message, options);
  },

  /**
   * Triggers an error notification.
   * @param {string} message The message to display.
   * @param {string} notificationStyle The current notification style from context.
   */
  error(message, notificationStyle) {
    const options = this.styleOptions[notificationStyle] || {};
    toast.error(message, options);
  },

  /**
   * Triggers an info notification.
   * @param {string} message The message to display.
   * @param {string} notificationStyle The current notification style from context.
   */
  info(message, notificationStyle) {
    const options = this.styleOptions[notificationStyle] || {};
    toast(message, options);
  }
};

export default notificationService;
